#!/usr/bin/env python3
"""ACS v4: profilage, identités, dépendances, comparaison exploratoire, validation.
Python standard library. Les scores de profils sont des hypothèses, pas des vérités métier.
"""
import argparse
import csv
import json
import math
import unicodedata
import uuid
from collections import defaultdict
from pathlib import Path

WEIGHTS = {'C': .35, 'I': .25, 'A': .20, 'T': .20}
PROFILES = {
    'active_directory': (['active directory','controleur de domaine','domain controller'], (10,10,9)),
    'pki': (['pki','certification','certificat'], (10,10,6)),
    'backup': (['backup','sauvegarde','storage','archivage'], (10,9,9)),
    'database': (['database','base de donnees','postgres','oracle','sql'], (8,9,8)),
    'web_public': (['web','frontend','portail'], (3,6,8)),
    'network_core': (['commutateur','switch','routeur','router','coeur de reseau'], (5,8,10)),
    'firewall': (['firewall','pare-feu','parefeu','vpn'], (6,9,10)),
    'workstation': (['workstation','poste de travail','laptop'], (2,3,3)),
}
ALIASES = {
    'nom': ('nom','nom_actif','asset_name','name','hostname','equipement'),
    'type': ('type','type_actif','role','asset_type','category','categorie'),
    'evenements_count': ('evenements_count','evenements','logs','events','events_count','frequence','count'),
    'C': ('c','confidentialite','confidentiality'),
    'I': ('i','integrite','integrity'),
    'A': ('a','disponibilite','availability'),
    'T': ('t','topologie','topology','connectivite'),
    'source_id': ('source_id','identifiant_source','asset_id','serial','numero_serie'),
    'source': ('source','outil','origine'),
}

def norm(v):
    s = unicodedata.normalize('NFD', str(v or '').lstrip('\ufeff'))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn').casefold().strip()

def canonicalize(row):
    lookup = {norm(k).replace(' ', '_'):v for k,v in row.items()}
    result = {}
    for key, variants in ALIASES.items():
        for alias in variants:
            if alias in lookup:
                result[key] = lookup[alias]
                break
    return result

def number(value, field, required=False):
    if value is None or str(value).strip() == '':
        if required: raise ValueError(f'Champ manquant : {field}')
        return None
    try: n = float(str(value).replace(',', '.'))
    except (TypeError, ValueError): raise ValueError(f'Valeur non numérique pour {field}: {value!r}')
    if not math.isfinite(n): raise ValueError(f'Valeur non finie pour {field}')
    return n

def read_csv(path):
    with open(path, encoding='utf-8-sig', newline='') as f:
        sample=f.read(4096); f.seek(0)
        try: dialect=csv.Sniffer().sniff(sample, delimiters=',;\t')
        except csv.Error: dialect='excel'
        return list(csv.DictReader(f, dialect=dialect))

def read_assets(path):
    p=Path(path)
    if p.suffix.lower()=='.csv': return read_csv(p)
    if p.suffix.lower()=='.xlsx':
        try: import pandas as pd
        except ImportError: raise RuntimeError('Pour les fichiers XLSX : pip install pandas openpyxl')
        return pd.read_excel(p).where(lambda df:df.notna(), None).to_dict('records')
    raise ValueError('Format pris en charge : .csv ou .xlsx')

def write_csv(path, rows, columns=None):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    cols=columns or (list(rows[0]) if rows else [])
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=cols,extrasaction='ignore');writer.writeheader();writer.writerows(rows)

def profile_for(asset_type):
    s=norm(asset_type)
    for name,(keywords,scores) in PROFILES.items():
        if any(k in s for k in keywords): return name,dict(zip('CIA',scores))
    return 'inconnu',{'C':5.,'I':5.,'A':5.}

def identity(a):
    """ID stable pour (source, source_id); repli sur (source, nom) signalé comme fragile."""
    source=norm(a.get('source') or 'inventaire')
    sid=norm(a.get('source_id'))
    name=norm(a.get('nom'))
    if not sid and not name: raise ValueError('Un nom ou source_id est requis')
    key=f'{source}|id:{sid}' if sid else f'{source}|nom:{name}'
    return str(uuid.uuid5(uuid.NAMESPACE_URL,'acs-v4|'+key)), 'source_id' if sid else 'nom_fragile'

def consolidate(rows):
    """Déduplication exacte sur identifiant source, ou nom au sein d'une même source.
    Aucune fusion probabiliste inter-sources n'est revendiquée.
    """
    assets={}
    for index,raw in enumerate(rows,1):
        a=canonicalize(raw)
        if not a.get('nom'): raise ValueError(f'Ligne {index}: nom obligatoire')
        uid,method=identity(a)
        a['id']=uid; a['identity_method']=method
        if uid in assets:
            old=assets[uid]
            for k,v in a.items():
                if v is not None and str(v).strip(): old[k]=v
        else: assets[uid]=a
    return list(assets.values())

def graph_from_csv(path, assets):
    """Arêtes non orientées pour la centralité de degré (une relation par paire)."""
    by_name={norm(a['nom']):a['id'] for a in assets}
    if len(by_name)!=len(assets): raise ValueError('Noms dupliqués entre sources : relations ambiguës')
    edges=set(); missing=[]
    for row in read_csv(path):
        u=by_name.get(norm(row.get('source')));v=by_name.get(norm(row.get('cible')))
        if not u or not v: missing.append(row); continue
        if u!=v: edges.add(tuple(sorted((u,v))))
    if missing: raise ValueError(f'{len(missing)} relations réfèrent à des actifs inconnus: {missing[:2]}')
    return edges

def topology(assets,edges):
    n=len(assets);deg=defaultdict(set)
    for u,v in edges: deg[u].add(v);deg[v].add(u)
    return {a['id']:round(1+9*len(deg[a['id']])/(n-1),4) if n>1 else 1. for a in assets}

def score_acs(scores, weights):
    if set(weights)!=set('CIAT') or any(not math.isfinite(v) or v<0 for v in weights.values()) or abs(sum(weights.values())-1)>1e-9:
        raise ValueError('Poids C,I,A,T non négatifs et somme=1 requis')
    return round(sum(weights[k]*scores[k] for k in 'CIAT'),2)

def level(s):
    return 'Critique' if s>=8 else 'Élevé' if s>=6 else 'Moyen' if s>=4 else 'Faible'

def process(rows, edges=None, weights=None):
    weights=weights or WEIGHTS
    assets=consolidate(rows)
    topo=topology(assets,edges) if edges is not None else None
    counts=[]
    for a in assets:
        c=number(a.get('evenements_count'),'evenements_count')
        if c is not None and (c<0 or c!=int(c)): raise ValueError('Nombre événements doit être un entier >=0')
        counts.append(c)
    # Un classement par fréquence est disponible seulement si toutes les observations sont mesurées.
    valid_counts=all(c is not None for c in counts) and sum(counts)>0
    levels=sorted(set(counts)) if valid_counts else []
    output=[]
    for a,cnt in zip(assets,counts):
        p,defaults=profile_for(a.get('type'))
        vals={}
        for k in 'CIA':
            v=number(a.get(k),k)
            vals[k]=v if v is not None else defaults[k]
            if not 1<=vals[k]<=10: raise ValueError(f'{a["nom"]}: {k} hors [1,10]')
        t_manual=number(a.get('T'),'T')
        if topo is not None:
            vals['T']=topo[a['id']];t_source='graphe'
        elif t_manual is not None:
            vals['T']=t_manual;t_source='inventaire'
        else:
            vals['T']=5.;t_source='neutre_sans_graphe'
        if not 1<=vals['T']<=10: raise ValueError(f'{a["nom"]}: T hors [1,10]')
        acs=score_acs(vals,weights)
        mu=round(cnt/sum(counts),6) if valid_counts else ''
        rank=levels.index(cnt)+1 if valid_counts else ''
        cr=round(rank/len(levels),4) if valid_counts else ''
        output.append({'id':a['id'],'nom':a['nom'],'type':a.get('type',''),
            'identite':a['identity_method'],'profil':p,'source_T':t_source,
            **{k:round(vals[k],4) for k in 'CIAT'},'evenements_count':cnt if cnt is not None else '',
            'ACS':acs,'niveau':level(acs),'freq_mu':mu,'freq_rang_normalise':cr,
            'ecart_ACS_freq10':round(acs-10*cr,2) if valid_counts else ''})
    return sorted(output,key=lambda r:(-r['ACS'],r['nom']))

def evaluate(rows, reference):
    """Référence binaire indépendante : colonne critique_reelle 0/1."""
    truth={norm(r['nom']):str(r['critique_reelle']).strip() for r in read_csv(reference)}
    if len(truth)!=len(rows) or any(norm(r['nom']) not in truth for r in rows):
        raise ValueError('La référence doit couvrir exactement tous les actifs')
    if any(v not in ('0','1') for v in truth.values()): raise ValueError('Référence attendue: 0 ou 1')
    results={}
    for model in ('ACS','freq_rang_normalise'):
        if model!='ACS' and any(r[model]=='' for r in rows):continue
        # Seuils pré-enregistrés: ACS>=6 ; rang fréquence >=0.6 (hypothèse exploratoire)
        threshold=6 if model=='ACS' else .6
        tp=fp=tn=fn=0
        for r in rows:
            actual=truth[norm(r['nom'])]=='1'; predicted=r[model]>=threshold
            if actual and predicted:tp+=1
            elif not actual and predicted:fp+=1
            elif not actual and not predicted:tn+=1
            else:fn+=1
        precision=tp/(tp+fp) if tp+fp else 0
        recall=tp/(tp+fn) if tp+fn else 0
        results[model]={'TP':tp,'FP':fp,'TN':tn,'FN':fn,
            'precision':round(precision,4),'rappel':round(recall,4),
            'F1':round(2*precision*recall/(precision+recall),4) if precision+recall else 0}
    return results

def main():
    ap=argparse.ArgumentParser(description='ACS v4 — étude expérimentale')
    ap.add_argument('inventaire',help='CSV ou XLSX')
    ap.add_argument('--relations',help='CSV source,cible (relations non orientées)')
    ap.add_argument('--reference',help='CSV nom,critique_reelle (0/1), établi indépendamment')
    ap.add_argument('--sortie',default='resultats_acs_v4.csv')
    ap.add_argument('--poids',default='0.35,0.25,0.20,0.20',help='C,I,A,T; somme 1')
    ap.add_argument('--sensibilite',action='store_true',help='Comparer 3 pondérations')
    args=ap.parse_args()
    values=[float(v) for v in args.poids.split(',')]
    if len(values)!=4: ap.error('--poids doit comporter 4 valeurs')
    weights=dict(zip('CIAT',values))
    data=read_assets(args.inventaire); assets=consolidate(data)
    edges=graph_from_csv(args.relations,assets) if args.relations else None
    rows=process(data,edges,weights)
    write_csv(args.sortie,rows)
    print(f'{len(rows)} actifs, {len(edges or [])} relations, résultats : {args.sortie}')
    if args.reference:
        metrics=evaluate(rows,args.reference)
        print('Métriques exploratoires (référence indépendante requise) :',json.dumps(metrics,ensure_ascii=False,indent=2))
        Path(args.sortie).with_suffix('.metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False),encoding='utf-8')
    if args.sensibilite:
        scenarios={'uniforme':dict.fromkeys('CIAT',.25),'confidentialite':WEIGHTS,
                   'disponibilite':{'C':.2,'I':.2,'A':.4,'T':.2}}
        sensitivity=[]
        for name,w in scenarios.items():
            for r in process(data,edges,w):sensitivity.append({'scenario':name,'nom':r['nom'],'ACS':r['ACS'],'niveau':r['niveau']})
        path=Path(args.sortie).with_suffix('.sensibilite.csv')
        write_csv(path,sensitivity)
        print('Analyse de sensibilité :',path)

if __name__=='__main__':main()
