"""Embedding models for text and image search using open-source models."""

from typing import List, Union
import numpy as np
from PIL import Image
from loguru import logger

from sentence_transformers import SentenceTransformer
import torch
from transformers import CLIPProcessor, CLIPModel


class TextEmbedding:
    """Text embedding using sentence-transformers."""

    def __init__(self, model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"):
        """
        Initialize text embedding model.

        Args:
            model_name: Name of the sentence-transformers model
        """
        logger.info(f"Loading text embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.dimension = self.model.get_sentence_embedding_dimension()
        logger.info(f"Text embedding dimension: {self.dimension}")

    def embed_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate embeddings for text.

        Args:
            text: Single text string or list of strings

        Returns:
            Numpy array of embeddings (shape: [n, dimension])
        """
        if isinstance(text, str):
            text = [text]

        embeddings = self.model.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embeddings

    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text string

        Returns:
            1D numpy array of embedding
        """
        embeddings = self.embed_text(text)
        return embeddings[0] if len(embeddings.shape) > 1 else embeddings


class ImageEmbedding:
    """Image and text embedding using CLIP."""

    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """
        Initialize CLIP embedding model.

        Args:
            model_name: Name of the CLIP model
        """
        logger.info(f"Loading CLIP model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")

        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.dimension = self.model.config.projection_dim
        logger.info(f"CLIP embedding dimension: {self.dimension}")

    def embed_image(self, image: Union[Image.Image, str, List[Union[Image.Image, str]]]) -> np.ndarray:
        """
        Generate embeddings for images.

        Args:
            image: PIL Image, image path, or list of images/paths

        Returns:
            Numpy array of embeddings (shape: [n, dimension])
        """
        if not isinstance(image, list):
            images = [image]
        else:
            images = image

        # Load images if paths are provided
        processed_images = []
        for img in images:
            if isinstance(img, str):
                img = Image.open(img).convert("RGB")
            processed_images.append(img)

        # Process images
        inputs = self.processor(
            images=processed_images,
            return_tensors="pt",
            padding=True
        ).to(self.device)

        # Generate embeddings
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            # Normalize embeddings
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        embeddings = image_features.cpu().numpy()
        return embeddings

    def embed_text_for_image_search(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Generate text embeddings in the same space as images (for cross-modal search).

        Args:
            text: Single text string or list of strings

        Returns:
            Numpy array of embeddings (shape: [n, dimension])
        """
        if isinstance(text, str):
            text = [text]

        # Process text
        inputs = self.processor(
            text=text,
            return_tensors="pt",
            padding=True,
            truncation=True
        ).to(self.device)

        # Generate embeddings
        with torch.no_grad():
            text_features = self.model.get_text_features(**inputs)
            # Normalize embeddings
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)

        embeddings = text_features.cpu().numpy()
        return embeddings

    def embed_single_image(self, image: Union[Image.Image, str]) -> np.ndarray:
        """
        Generate embedding for a single image.

        Args:
            image: PIL Image or image path

        Returns:
            1D numpy array of embedding
        """
        embeddings = self.embed_image(image)
        return embeddings[0] if len(embeddings.shape) > 1 else embeddings


class EmbeddingManager:
    """Manages both text and image embedding models."""

    def __init__(
        self,
        text_model_name: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
        image_model_name: str = "openai/clip-vit-base-patch32"
    ):
        """
        Initialize embedding manager with text and image models.

        Args:
            text_model_name: Name of the text embedding model
            image_model_name: Name of the CLIP model
        """
        self.text_embedder = TextEmbedding(text_model_name)
        self.image_embedder = ImageEmbedding(image_model_name)

    @property
    def text_dimension(self) -> int:
        """Get text embedding dimension."""
        return self.text_embedder.dimension

    @property
    def image_dimension(self) -> int:
        """Get image embedding dimension."""
        return self.image_embedder.dimension

    def create_classification_embedding(self, classification_text: str) -> np.ndarray:
        """
        Create embedding for patent classification text (code + titles).

        Args:
            classification_text: Combined text from code and descriptions

        Returns:
            1D numpy array of embedding
        """
        return self.text_embedder.embed_single(classification_text)
