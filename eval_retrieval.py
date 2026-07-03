"""Avaliação do retrieval contra um gold set: python eval_retrieval.py

Mede hit@1/3/5 e MRR do pipeline real (obter_artigos) sobre perguntas
com artigo correto verificado no texto. Usar após mexer no chunking,
modelo de embeddings ou pesos RRF.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import assistente_vetorial as av

# (pergunta, artigos aceites)
GOLD = [
    ("Qual é o limite de velocidade em autoestrada?", {"art27"}),
    ("É obrigatório usar cinto de segurança?", {"art82"}),
    ("Posso usar telemóvel ao conduzir?", {"art84"}),
    ("Posso conduzir com auscultadores?", {"art84"}),
    ("Qual a distância mínima para ultrapassar uma bicicleta?", {"art38"}),
    ("Qual é o limite de álcool no sangue?", {"art81"}),
    ("Como devo circular numa rotunda?", {"art14A"}),
    ("Onde é proibido estacionar?", {"art49", "art50"}),
    ("Quando é proibido ultrapassar?", {"art41"}),
    ("Onde é proibida a inversão do sentido de marcha?", {"art45"}),
    ("Que documentos devo levar quando conduzo?", {"art85"}),
    ("Quando devo usar as luzes médios?", {"art60", "art61"}),
    ("Como transportar crianças no automóvel?", {"art55"}),
    ("É obrigatório ter seguro automóvel?", {"art150"}),
    ("O que fazer em caso de avaria do carro?", {"art87", "art88"}),
    ("Quando posso buzinar?", {"art22"}),
    ("Crianças podem andar de bicicleta no passeio?", {"art17"}),
    ("Qual a distância de segurança entre veículos?", {"art18"}),
    ("Quem tem prioridade num cruzamento?", {"art30", "art31"}),
    ("Posso fazer marcha atrás numa rotunda?", {"art47"}),
]


def main():
    av.init()
    hit1 = hit3 = hit5 = mrr = 0.0
    falhas = []
    for pergunta, gold in GOLD:
        top = [item['artigo']['artigo_id'] for item in av.obter_artigos(pergunta)]
        pos = next((i for i, aid in enumerate(top, 1) if aid in gold), None)
        if pos:
            mrr += 1 / pos
            hit1 += pos <= 1
            hit3 += pos <= 3
            hit5 += pos <= 5
        else:
            falhas.append(pergunta)

    n = len(GOLD)
    print("\n" + "=" * 60)
    print(f"hit@1={hit1 / n:.2f}  hit@3={hit3 / n:.2f}  hit@5={hit5 / n:.2f}  MRR={mrr / n:.3f}  (n={n})")
    for f in falhas:
        print(f"  FALHA: {f}")


if __name__ == "__main__":
    main()
