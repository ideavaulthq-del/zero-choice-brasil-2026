#!/usr/bin/env python3
"""Lê apenas o JSON oficial do TSE e produz results.json para o estúdio.
Falha sem publicar se a resposta estiver incompleta ou inconsistente.
"""
import json, os, pathlib, re, urllib.request, datetime
URL = 'https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'results.json'

def integer(value):
    s = str(value)
    if not re.fullmatch(r'\d+', s): raise ValueError('Número inválido')
    return int(s)

def transform(d):
    if str(d.get('ele')) != '6258' or str(d.get('t')) != '2' or d.get('cdabr') != 'br':
        raise ValueError('Eleição, turno ou abrangência incorretos')
    offices = [x for x in d.get('carg',[]) if str(x.get('cd')) == '1']
    if len(offices) != 1: raise ValueError('Cargo presidente ausente')
    candidates = {}
    for group in offices[0].get('agr',[]):
        for party in group.get('par',[]):
            for cand in party.get('cand',[]):
                num = str(cand.get('n'))
                if num in ('13','22'):
                    if num in candidates: raise ValueError('Candidato duplicado')
                    candidates[num] = integer(cand.get('vap',''))
    if set(candidates) != {'13','22'}: raise ValueError('Candidatos esperados não encontrados')
    counted = integer(d.get('s',{}).get('st',''))
    total = integer(d.get('s',{}).get('ts',''))
    if total <= 0 or counted > total: raise ValueError('Totalização inconsistente')
    valid = integer(d.get('v',{}).get('vv',''))
    if candidates['13']+candidates['22'] != valid:
        raise ValueError('Soma dos candidatos não corresponde aos votos válidos')
    date, time = d.get('dt'), d.get('ht')
    if not date or not time: raise ValueError('Sem hora oficial')
    ts = datetime.datetime.strptime(date+' '+time,'%d/%m/%Y %H:%M:%S').replace(tzinfo=datetime.timezone(datetime.timedelta(hours=-3)))
    if ts.date() != datetime.date(2026,10,25): raise ValueError('Data fora do dia do 2.º turno')
    if ts > datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(minutes=5):
        raise ValueError('Hora oficial no futuro')
    return {'status':'verified' if counted>0 and valid>0 else 'pending',
        'electionId':'6258','office':'president','scope':'br',
        'votesA':candidates['13'],'votesB':candidates['22'],
        'sectionsCounted':counted,'sectionsTotal':total,
        'sectionsPercent':round(100*counted/total,2),
        'source':'TSE · resultados.tse.jus.br','sourceUrl':URL,
        'updatedAt':ts.isoformat(), 'sourceGenerationId':str(d.get('idg',''))}

def main():
    req=urllib.request.Request(URL,headers={'User-Agent':'ZERO-CHOICE-BRASIL-2026/22 (+independent-election-display)','Accept':'application/json'})
    with urllib.request.urlopen(req,timeout=25) as response:
        if response.status != 200: raise RuntimeError('Erro HTTP')
        raw=response.read(1024*1024+1)
        if len(raw)>1024*1024: raise ValueError('Ficheiro demasiado grande')
    result=transform(json.loads(raw))
    if result['status'] != 'verified':
        print('Ainda sem votos oficiais; manter estado anterior.');return
    if OUT.exists():
        try:
            old=json.loads(OUT.read_text(encoding='utf-8'))
            if old.get('status')=='verified':
                if old.get('sourceGenerationId') == result['sourceGenerationId']: return
                if old.get('updatedAt','') > result['updatedAt']:
                    raise ValueError('Resposta mais antiga que o resultado publicado')
        except (ValueError,json.JSONDecodeError) as e: raise
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Atualização oficial validada:',result['updatedAt'])
if __name__=='__main__':main()
