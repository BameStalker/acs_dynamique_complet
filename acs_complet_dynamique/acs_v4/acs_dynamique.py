#!/usr/bin/env python3
"""ACS dynamique: inventaire persistant, actifs entrants, graphe et variations de scores.
Exécuter depuis le dossier du projet : python acs_dynamique.py --aide (ou -h).
Dépendances: bibliothèque standard (CSV); acs_v4.py dans le même dossier.
"""
import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from acs_v4 import (read_csv, write_csv, consolidate, graph_from_csv, process,
                    identity, canonicalize, WEIGHTS, norm)

ASSET_COLS=['nom','type','source','source_id','evenements_count','confidentialite','integrite','disponibilite','topologie']
EDGE_COLS=['source','cible']

def save_csv(path,rows,cols):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    write_csv(tmp,rows,cols)
    tmp.replace(path)

def load_inventory(path):
    return read_csv(path) if Path(path).exists() else []

def load_edges(path):
    return read_csv(path) if Path(path).exists() else []

def evaluate_state(assets, relations, weights):
    unique=consolidate(assets)
    # Toutes les relations sont vérifiées, y compris les relations dupliquées.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        temp=Path(td)/'relations.csv'
        write_csv(temp,relations,EDGE_COLS)
        edges=graph_from_csv(temp,unique)
    return process(assets,edges,weights)

def build_weights(raw):
    vals=[float(x.strip()) for x in raw.split(',')]
    if len(vals)!=4: raise ValueError('Quatre poids attendus : C,I,A,T')
    w=dict(zip('CIAT',vals))
    from acs_v4 import score_acs
    score_acs(dict.fromkeys('CIAT',5),w)
    return w

def merge_asset(existing,incoming):
    """Identité fiable par source+source_id; sinon repli nom/source (renommage non sûr)."""
    a=canonicalize(incoming)
    for short,long_name in [('C','confidentialite'),('I','integrite'),('A','disponibilite'),('T','topologie')]:
        if short in a: a[long_name]=a.pop(short)
    if not a.get('nom'):raise ValueError('Le nouvel actif doit avoir un nom')
    new_id,_=identity(a)
    for item in existing:
        old_id,_=identity(canonicalize(item))
        if old_id==new_id:
            # Ne remplacer que les valeurs explicitement fournies.
            for key,val in a.items():
                if val is not None and str(val).strip()!='':
                    item[key]=val
            return 'mis_a_jour'
    # Bloquer les collisions de noms: les arêtes utilisent des noms uniques.
    if any(norm(item['nom'])==norm(a['nom']) for item in existing):
        raise ValueError('Nom déjà utilisé par un autre identifiant: relation ambiguë')
    existing.append({key:a.get(key,'') for key in ASSET_COLS})
    return 'ajoute'

def apply_relations(existing, relations, new_name, neighbors):
    known={norm(a['nom']) for a in existing}
    if norm(new_name) not in known:raise ValueError('Actif absent après mise à jour')
    seen={tuple(sorted((norm(r['source']),norm(r['cible'])))) for r in relations}
    for name in neighbors:
        if norm(name) not in known:raise ValueError(f'Voisin inconnu : {name}')
        if norm(name)==norm(new_name):continue
        pair=tuple(sorted((norm(new_name),norm(name))))
        if pair not in seen:
            relations.append({'source':new_name,'cible':name})
            seen.add(pair)

def write_outputs(args,old,new,action):
    dest=Path(args.sortie)
    save_csv(dest,new,list(new[0]) if new else ['nom','ACS'])
    previous={r['id']:r for r in old}
    changes=[]
    for r in new:
        prev=previous.get(r['id'])
        changes.append({'nom':r['nom'],'id':r['id'],
                        'ACS_avant':prev['ACS'] if prev else '',
                        'ACS_apres':r['ACS'],
                        'variation':round(r['ACS']-prev['ACS'],4) if prev else '',
                        'statut':'nouveau' if prev is None else 'existant'})
    save_csv(args.variations,changes,['nom','id','ACS_avant','ACS_apres','variation','statut'])
    print(json.dumps({'operation':action,'actifs':len(new),
                      'resultats':str(dest),'variations':str(args.variations)},ensure_ascii=False,indent=2))
    for c in changes:
        if c['statut']=='nouveau' or c['variation']!=0:
            print(f"{c['nom']}: {c['ACS_avant']} -> {c['ACS_apres']} (Δ={c['variation']})")

def main():
    p=argparse.ArgumentParser(description='ACS dynamique : calcul et ajout d’actifs entrants')
    p.add_argument('--inventaire',default='data/inventaire_synthetique.csv')
    p.add_argument('--relations',default='data/relations_synthetiques.csv')
    p.add_argument('--sortie',default='results/acs_dynamique.csv')
    p.add_argument('--variations',default='results/variations_acs.csv')
    p.add_argument('--poids',default='0.35,0.25,0.20,0.20')
    sub=p.add_subparsers(dest='commande',required=True)
    sub.add_parser('calculer',help='Recalculer ACS pour tout l’inventaire')
    add=sub.add_parser('ajouter',help='Ajouter ou actualiser un actif et recalculer ACS')
    add.add_argument('--nom',required=True)
    add.add_argument('--type',default='Inconnu')
    add.add_argument('--source',default='inventaire')
    add.add_argument('--source-id',default='')
    add.add_argument('--c',type=float)
    add.add_argument('--i',type=float)
    add.add_argument('--a',type=float)
    add.add_argument('--evenements',type=int)
    add.add_argument('--voisins',default='',help='Noms exacts séparés par des virgules')
    args=p.parse_args()
    weights=build_weights(args.poids)
    assets=load_inventory(args.inventaire)
    relations=load_edges(args.relations)
    old=evaluate_state(assets,relations,weights) if assets else []
    action='recalcul'
    if args.commande=='ajouter':
        incoming={'nom':args.nom,'type':args.type,'source':args.source,'source_id':args.source_id}
        for key,val in [('confidentialite',args.c),('integrite',args.i),('disponibilite',args.a),('evenements_count',args.evenements)]:
            if val is not None:incoming[key]=val
        action=merge_asset(assets,incoming)
        neighbors=[x.strip() for x in args.voisins.split(',') if x.strip()]
        apply_relations(assets,relations,args.nom,neighbors)
    new=evaluate_state(assets,relations,weights)
    if args.commande=='ajouter':
        save_csv(args.inventaire,assets,ASSET_COLS)
        save_csv(args.relations,relations,EDGE_COLS)
    write_outputs(args,old,new,action)

if __name__=='__main__':
    try:main()
    except (ValueError,KeyError,FileNotFoundError) as e:
        import sys
        print('Erreur:',e,file=sys.stderr)
        sys.exit(2)
