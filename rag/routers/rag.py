# -*- coding: utf-8 -*-
import os
import tempfile
import boto3
import logging
from typing import List
from dataclasses import dataclass
from langchain_community.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Константы для S3
S3_ENDPOINT = os.getenv('S3_ENDPOINT', 'https://storage.yandexcloud.net')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
S3_BUCKET = os.getenv('S3_BUCKET')
S3_PREFIX = os.getenv('S3_PREFIX', 'legal_docs/')

# Константы для векторного поиска
VECTORSTORE_PATH = "./vectorstore_faiss"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TOP_K_RESULTS = 3


@dataclass
class RetrievedDocument:
    """Класс для хранения найденного документа с метаданными"""
    content: str
    source: str
    score: float
    rank: int


class YandexRAG:
    """RAG система для работы с Yandex Object Storage"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(YandexRAG, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.s3_client = None
        self.embeddings = None
        self.vectorstore = None
        self._init_s3_client()
        self._init_embeddings()
        self._initialized = True

    def _init_s3_client(self):
        """Инициализация S3 клиента для Yandex Object Storage"""
        try:
            if not all([S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET]):
                logger.error("Не все S3 переменные окружения установлены")
                return

            self.s3_client = boto3.client(
                's3',
                endpoint_url=S3_ENDPOINT,
                aws_access_key_id=S3_ACCESS_KEY,
                aws_secret_access_key=S3_SECRET_KEY,
                region_name='ru-central1'
            )
            logger.info("S3 клиент успешно инициализирован")
        except Exception as e:
            logger.error(f"Ошибка инициализации S3 клиента: {e}")

    def _init_embeddings(self):
        """Инициализация модели эмбеддингов"""
        try:
            self.embeddings = HuggingFaceEmbeddings(
                model_name=EMBEDDING_MODEL,
                model_kwargs={'device': 'cpu'}
            )
            logger.info(f"Модель эмбеддингов {EMBEDDING_MODEL} загружена")
        except Exception as e:
            logger.error(f"Ошибка загрузки модели эмбеддингов: {e}")

    def download_docs_from_s3(self) -> List[str]:
        """Загрузка документов из Yandex Object Storage"""
        if not self.s3_client:
            logger.error("S3 клиент не инициализирован")
            return []

        try:
            response = self.s3_client.list_objects_v2(
                Bucket=S3_BUCKET,
                Prefix=S3_PREFIX
            )

            if 'Contents' not in response:
                logger.warning("Нет документов в S3 bucket")
                return []

            tmpdir = tempfile.mkdtemp()
            local_files = []

            for obj in response['Contents']:
                key = obj['Key']
                # Поддерживаем различные форматы файлов
                if not any(key.endswith(ext) for ext in ['.txt', '.md', '.rtf']):
                    continue

                local_path = os.path.join(tmpdir, os.path.basename(key))
                try:
                    self.s3_client.download_file(S3_BUCKET, key, local_path)
                    local_files.append(local_path)
                    logger.debug(f"Загружен файл: {key}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки файла {key}: {e}")

            logger.info(f"Загружено {len(local_files)} файлов из S3")
            return local_files

        except Exception as e:
            logger.error(f"Ошибка загрузки из S3: {e}")
            return []

    def load_and_split_documents(self, files: List[str]) -> List[Document]:
        """Загрузка и разбиение документов на чанки"""
        docs = []

        for file_path in files:
            try:
                loader = TextLoader(file_path, encoding="utf-8")
                file_docs = loader.load()

                for doc in file_docs:
                    doc.metadata['source_file'] = os.path.basename(file_path)

                docs.extend(file_docs)
                logger.debug(f"Загружен документ: {file_path}")

            except Exception as e:
                logger.error(f"Ошибка загрузки файла {file_path}: {e}")

        # Фильтруем пустые документы
        docs = [doc for doc in docs if doc.page_content.strip()]

        if not docs:
            logger.warning("Нет валидных документов для обработки")
            return []

        # Разбиваем документы на чанки
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

        chunks = splitter.split_documents(docs)
        logger.info(f"Создано {len(chunks)} чанков из {len(docs)} документов")

        return chunks

    def build_vectorstore(self, chunks: List[Document]) -> bool:
        """Создание векторного хранилища"""
        if not chunks:
            logger.error("Нет чанков для создания векторного хранилища")
            return False

        if not self.embeddings:
            logger.error("Модель эмбеддингов не инициализирована")
            return False

        try:
            self.vectorstore = FAISS.from_documents(chunks, self.embeddings)

            # Сохраняем векторное хранилище на диск
            os.makedirs(os.path.dirname(VECTORSTORE_PATH), exist_ok=True)
            self.vectorstore.save_local(VECTORSTORE_PATH)

            logger.info("Векторное хранилище успешно создано и сохранено")
            return True

        except Exception as e:
            logger.error(f"Ошибка создания векторного хранилища: {e}")
            return False

    def load_vectorstore(self) -> bool:
        """Загрузка векторного хранилища с диска"""
        if not self.embeddings:
            logger.error("Модель эмбеддингов не инициализирована")
            return False

        try:
            if not os.path.exists(f"{VECTORSTORE_PATH}/index.faiss"):
                logger.info("Векторное хранилище не найдено, требуется инициализация")
                return False

            self.vectorstore = FAISS.load_local(
                VECTORSTORE_PATH,
                self.embeddings,
                allow_dangerous_deserialization=True
            )

            logger.info("Векторное хранилище успешно загружено")
            return True

        except Exception as e:
            logger.error(f"Ошибка загрузки векторного хранилища: {e}")
            return False

    def initialize_rag_system(self) -> bool:
        """Полная инициализация RAG системы"""
        logger.info("Начинаем инициализацию RAG системы...")

        # Пытаемся загрузить существующее векторное хранилище
        if self.load_vectorstore():
            return True

        # Если не удалось, создаем новое
        logger.info("Создаем новое векторное хранилище...")

        # Загружаем документы из S3
        files = self.download_docs_from_s3()
        if not files:
            logger.error("Не удалось загрузить файлы из S3")
            return False

        # Обрабатываем документы
        chunks = self.load_and_split_documents(files)
        if not chunks:
            logger.error("Не удалось создать чанки документов")
            return False

        # Создаем векторное хранилище
        return self.build_vectorstore(chunks)

    def retrieve_documents(self, query: str, top_k: int = TOP_K_RESULTS) -> List[RetrievedDocument]:
        """Поиск релевантных документов с ранжированием"""
        if not self.vectorstore:
            if not self.load_vectorstore():
                logger.error("Векторное хранилище недоступно")
                return []

        try:
            docs_with_scores = self.vectorstore.similarity_search_with_score(
                query, k=top_k
            )

            retrieved_docs = []
            for rank, (doc, score) in enumerate(docs_with_scores, 1):
                retrieved_doc = RetrievedDocument(
                    content=doc.page_content,
                    source=doc.metadata.get('source_file', 'unknown'),
                    score=float(score),
                    rank=rank
                )
                retrieved_docs.append(retrieved_doc)

            logger.info(f"Найдено {len(retrieved_docs)} релевантных документов для запроса")
            return retrieved_docs

        except Exception as e:
            logger.error(f"Ошибка поиска документов: {e}")
            return []

    def format_context_for_llm(self, retrieved_docs: List[RetrievedDocument]) -> str:
        """Форматирование контекста для передачи в LLM"""
        if not retrieved_docs:
            return "Релевантная информация в документах не найдена."

        context_parts = []
        for doc in retrieved_docs:
            context_part = f"""
            Документ #{doc.rank} (релевантность: {doc.score:.3f})
            Источник: {doc.source}
            Содержание: {doc.content}
            """
            context_parts.append(context_part.strip())

        return "\n\n" + "=" * 50 + "\n\n".join(context_parts)

    def search(self, query: str, top_k: int = TOP_K_RESULTS) -> tuple[str, List[RetrievedDocument]]:
        """Основной метод для поиска и форматирования результатов"""
        try:
            retrieved_docs = self.retrieve_documents(query, top_k)
            formatted_context = self.format_context_for_llm(retrieved_docs)

            return formatted_context, retrieved_docs

        except Exception as e:
            logger.error(f"Ошибка в RAG поиске: {e}")
            return "Ошибка при поиске в документах.", []

    def update_vectorstore(self) -> bool:
        """Принудительное обновление векторного хранилища"""
        logger.info("Принудительное обновление векторного хранилища...")

        files = self.download_docs_from_s3()
        if not files:
            return False

        chunks = self.load_and_split_documents(files)
        if not chunks:
            return False

        return self.build_vectorstore(chunks)