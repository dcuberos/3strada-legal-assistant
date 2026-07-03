"""Testes mínimos: python test_basico.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

import assistente_vetorial as av
import data_raw
from hybrid_retrieval import HybridRetriever, _tokenize_pt


def test_estruturar_artigos():
    texto = """Título I
Disposições gerais
Capítulo I
Princípios
Artigo 1.º
Definições legais
Para os efeitos deste Código:
a) «Autoestrada» - via pública;
Artigo 2.º
Âmbito
1 - Aplica-se ao trânsito.
2 - (Revogado.)
Alterações ao artigo
Secção II
Velocidade
Artigo 3.º-A
Exceções
(Revogado.)
"""
    artigos = data_raw.estruturar_artigos(texto)
    assert len(artigos) == 3, artigos

    a1, a2, a3 = artigos
    assert a1['artigo_id'] == 'art1' and a1['numero'] == 1 and a1['sufixo'] == ''
    assert a1['epigrafe'] == 'Definições legais'
    assert a1['capitulo'] == 'Princípios' and a1['seccao'] is None
    assert a1['titulo'] == 'Artigo 1.º — Definições legais'
    assert not a1['revogado']

    assert a2['numero'] == 2
    assert 'Alterações ao artigo' not in a2['conteudo']
    assert '[REVOGADO]' in a2['conteudo']  # número revogado, artigo não
    assert not a2['revogado']

    assert a3['artigo_id'] == 'art3A' and a3['sufixo'] == 'A'
    assert a3['seccao'] == 'Velocidade'
    assert a3['revogado']


def test_tokenize_pt():
    tokens = _tokenize_pt('O limite de velocidade nas autoestradas!')
    assert 'de' not in tokens and 'o' not in tokens  # stopwords removidas
    assert len(tokens) == 3, tokens  # limite, velocidade, autoestradas (stemmed)
    assert _tokenize_pt('velocidade') == _tokenize_pt('velocidades')  # stemming


def test_rrf():
    scores = HybridRetriever._rrf([['a', 'b'], ['b', 'a']])
    assert abs(scores['a'] - (1 / 61 + 1 / 62)) < 1e-9
    assert scores['a'] == scores['b']

    # peso 2x na segunda lista favorece o seu primeiro colocado
    scores = HybridRetriever._rrf([['a', 'b'], ['b', 'a']], weights=[1.0, 2.0])
    assert scores['b'] > scores['a']


def test_lookup_por_numero():
    av.artigos = [
        {'artigo_id': 'art27', 'numero': 27, 'sufixo': '', 'titulo': 'Artigo 27.º — Limites'},
        {'artigo_id': 'art14A', 'numero': 14, 'sufixo': 'A', 'titulo': 'Artigo 14.º-A — Rotundas'},
    ]
    assert av._lookup_por_numero('o que diz o artigo 27?')[0]['artigo']['artigo_id'] == 'art27'
    assert av._lookup_por_numero('artigo 14.º-A')[0]['artigo']['artigo_id'] == 'art14A'
    assert av._lookup_por_numero('artigo 14-a')[0]['artigo']['artigo_id'] == 'art14A'
    assert av._lookup_por_numero('artigo 99') is None  # não existe
    assert av._lookup_por_numero('limite de velocidade') is None  # sem referência


if __name__ == '__main__':
    test_estruturar_artigos()
    test_tokenize_pt()
    test_rrf()
    test_lookup_por_numero()
    print('OK - todos os testes passaram')
