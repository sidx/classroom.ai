from config.logging import logger
from indexing.extractor import AzureDevopsRepoExtractor, DataExtractor, GitLabRepoExtractor, GitHubRepoExtractor, \
    QuipExtractor
from indexing.loaders import ElasticSearchLoader, DataLoader
from indexing.transformers import RepoTransformer, DataTransformer, QuipTransformer


class KnowledgeBaseFactory:
    EXTRACTORS = {
        "azure_devops": AzureDevopsRepoExtractor,
        "gitlab": GitLabRepoExtractor,
        "github": GitHubRepoExtractor,
        "quip": QuipExtractor
    }

    TRANSFORMERS = {
        "repo_transformer": RepoTransformer,
        "quip_transformer": QuipTransformer
    }

    LOADERS = {
        "elasticsearch": ElasticSearchLoader
    }

    @staticmethod
    def get_extractor(name: str, **kwargs) -> DataExtractor:
        logger.info(f"Creating extractor for {name}")
        extractor_cls = KnowledgeBaseFactory.EXTRACTORS.get(name)
        if not extractor_cls:
            raise ValueError(f"Unknown extractor: {name}")
        return extractor_cls(**kwargs)

    @staticmethod
    def get_transformer(name: str) -> DataTransformer:
        logger.info(f"Creating transformer for {name}")
        transformer_cls = KnowledgeBaseFactory.TRANSFORMERS.get(name)
        if not transformer_cls:
            raise ValueError(f"Unknown transformer: {name}")
        return transformer_cls()

    @staticmethod
    def get_loader(name: str, **kwargs) -> DataLoader:
        logger.info(f"Creating loader for {name}")
        loader_cls = KnowledgeBaseFactory.LOADERS.get(name)
        if not loader_cls:
            raise ValueError(f"Unknown loader: {name}")
        return loader_cls(**kwargs)
