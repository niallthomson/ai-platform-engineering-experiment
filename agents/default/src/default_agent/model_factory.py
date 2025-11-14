import logging
from strands.models import Model, BedrockModel
from strands.models.openai import OpenAIModel
from .config import ModelConfig


def create_model(config: ModelConfig) -> Model:
    logging.info(f"Model provider: {config.provider}")
    logging.info(f"Model ID: {config.model_id}")

    match config.provider:
        case "bedrock":
            logging.info(f"Bedrock region: {config.bedrock.region}")

            return BedrockModel(
                model_id=config.model_id,
                temperature=config.temperature,
                top_p=config.temperature,
                region_name=config.bedrock.region,
            )

        case "openai":
            logging.info(f"OpenAI base URL: {config.openai.base_url}")

            return OpenAIModel(
                model_id=config.model_id,
                client_args={
                    "api_key": config.openai.api_key,
                    "base_url": config.openai.base_url,
                },
                params={"temperature": config.temperature, "top_p": config.temperature},
            )

        case _:
            logging.error(f"Unknown model provider: {config.provider}")
            exit(1)
