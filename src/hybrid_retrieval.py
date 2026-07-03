import os
import pickle
import re

import nltk
from nltk.corpus import stopwords
from nltk.stem import RSLPStemmer
from rank_bm25 import BM25Okapi

nltk.download("stopwords", quiet=True)
nltk.download("rslp", quiet=True)

_stopwords_pt = set(stopwords.words("portuguese"))
_stemmer = RSLPStemmer()


def _tokenize_pt(text: str) -> list:
    tokens = re.sub(r"[^\w\s]", " ", text.lower()).split()
    return [_stemmer.stem(t) for t in tokens if t not in _stopwords_pt and len(t) > 1]


class HybridRetriever:
    """
    Retrieval híbrido: ChromaDB (semântico) + BM25 (keyword), fundidos via RRF.

    Uso:
        retriever = HybridRetriever(collection, artigos, "data/bm25_index.pkl")
        resultados = retriever.retrieve("limite de velocidade na autoestrada", k=5)
    """

    def __init__(self, collection, artigos: list, index_path: str):
        """
        Args:
            collection: ChromaDB collection já inicializada (com embedding_function).
            artigos:    Lista de dicts {"titulo": str, "conteudo": str}.
            index_path: Caminho para guardar/carregar o índice BM25 em pickle.
        """
        self.collection = collection
        self.artigos = artigos
        self.index_path = index_path
        self._bm25 = None
        self._corpus_ids = None  # IDs do ChromaDB na mesma ordem do corpus BM25
        self._load_or_build()

    # ------------------------------------------------------------------
    # Construção e persistência do índice
    # ------------------------------------------------------------------

    def _load_or_build(self):
        if os.path.exists(self.index_path):
            print("Carregando indice BM25 do disco...")
            with open(self.index_path, "rb") as f:
                data = pickle.load(f)
            self._bm25 = data["bm25"]
            self._corpus_ids = data["corpus_ids"]
            print(f"Indice BM25 carregado ({len(self._corpus_ids)} documentos)")
        else:
            self._build_and_save()

    def _build_and_save(self):
        print("Construindo indice BM25 (primeira vez)...")
        result = self.collection.get(include=["documents", "metadatas"])
        ids = result["ids"]
        documents = result["documents"]

        tokenized_corpus = [_tokenize_pt(doc) for doc in documents]
        self._bm25 = BM25Okapi(tokenized_corpus)
        self._corpus_ids = ids

        index_dir = os.path.dirname(self.index_path)
        if index_dir:
            os.makedirs(index_dir, exist_ok=True)

        with open(self.index_path, "wb") as f:
            pickle.dump({"bm25": self._bm25, "corpus_ids": self._corpus_ids}, f)

        print(f"Indice BM25 guardado em '{self.index_path}' ({len(ids)} documentos)")

    # ------------------------------------------------------------------
    # Reciprocal Rank Fusion
    # ------------------------------------------------------------------

    @staticmethod
    def _rrf(rankings: list, weights: list = None, k: int = 60) -> dict:
        """
        Reciprocal Rank Fusion com pesos por lista.

        Args:
            rankings: Lista de listas de IDs ordenados por relevância (melhor primeiro).
            weights:  Peso de cada lista (default: todas com peso 1).
            k:        Constante de suavização (default=60).

        Returns:
            Dict {doc_id: rrf_score}.
        """
        if weights is None:
            weights = [1.0] * len(rankings)
        scores = {}
        for ranking, weight in zip(rankings, weights):
            for rank, doc_id in enumerate(ranking, start=1):
                scores[doc_id] = scores.get(doc_id, 0.0) + weight / (k + rank)
        return scores

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def retrieve(self, query: str, k: int = 5) -> list:
        """
        Retrieval híbrido com RRF.

        Retorna uma lista de dicts compatível com encontrar_artigos_relevantes:
            [{"artigo": {...}, "relevancia": float, "distancia": float | None}]

        Args:
            query: Pergunta do utilizador.
            k:     Número de documentos a devolver.

        Returns:
            Top-k documentos fundidos, ordenados por RRF score descendente.
        """
        n_candidates = max(k * 10, 50)
        n_candidates = min(n_candidates, self.collection.count())

        # --- Retrieval semântico (ChromaDB) ---
        chroma_result = self.collection.query(
            query_texts=[query],
            n_results=n_candidates
        )
        chroma_ranking = chroma_result["ids"][0]
        chroma_distances = {
            doc_id: dist
            for doc_id, dist in zip(chroma_result["ids"][0], chroma_result["distances"][0])
        }

        # --- Retrieval BM25 ---
        tokenized_query = _tokenize_pt(query)
        bm25_scores = self._bm25.get_scores(tokenized_query)
        bm25_ranked_indices = sorted(
            range(len(bm25_scores)),
            key=lambda i: bm25_scores[i],
            reverse=True
        )[:n_candidates]
        bm25_ranking = [self._corpus_ids[i] for i in bm25_ranked_indices]

        # --- Reciprocal Rank Fusion (BM25 com peso 2x por ser mais preciso lexicalmente) ---
        rrf_scores = self._rrf([chroma_ranking, bm25_ranking], weights=[1.0, 2.0])

        top_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)

        # --- Montar resultado: reagrupar chunks pelo artigo de origem ---
        # id do chunk = "indice_chunk"; o primeiro chunk (melhor RRF) representa o artigo
        results = []
        vistos = set()
        for doc_id in top_ids:
            indice = int(doc_id.split("_")[0])
            if indice in vistos:
                continue
            vistos.add(indice)
            results.append({
                "artigo": self.artigos[indice],
                "relevancia": rrf_scores[doc_id],
                "distancia": chroma_distances.get(doc_id),
            })
            if len(results) == k:
                break

        return results
