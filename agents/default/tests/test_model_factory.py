import pytest
from unittest.mock import Mock, patch
from default_agent.model_factory import create_model
from default_agent.config import ModelConfig


@pytest.fixture
def mock_bedrock_config():
    config = Mock(spec=ModelConfig)
    config.provider = "bedrock"
    config.model_id = "test-model"
    config.temperature = 0.7
    config.bedrock = Mock(region="us-west-2")
    return config


@pytest.fixture
def mock_openai_config():
    config = Mock(spec=ModelConfig)
    config.provider = "openai"
    config.model_id = "gpt-4"
    config.temperature = 0.5
    config.openai = Mock(api_key="test-key", base_url="https://api.openai.com")
    return config


@patch("default_agent.model_factory.BedrockModel")
def test_create_bedrock_model(mock_bedrock_model, mock_bedrock_config):
    create_model(mock_bedrock_config)
    
    mock_bedrock_model.assert_called_once()
    call_kwargs = mock_bedrock_model.call_args.kwargs
    assert call_kwargs["model_id"] == "test-model"
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["region_name"] == "us-west-2"


@patch("default_agent.model_factory.OpenAIModel")
def test_create_openai_model(mock_openai_model, mock_openai_config):
    create_model(mock_openai_config)
    
    mock_openai_model.assert_called_once()
    call_kwargs = mock_openai_model.call_args.kwargs
    assert call_kwargs["model_id"] == "gpt-4"
    assert call_kwargs["client_args"]["api_key"] == "test-key"
    assert call_kwargs["client_args"]["base_url"] == "https://api.openai.com"
    assert call_kwargs["params"]["temperature"] == 0.5


def test_create_model_unknown_provider():
    config = Mock(spec=ModelConfig)
    config.provider = "unknown"
    config.model_id = "test-model"
    
    with pytest.raises(SystemExit):
        create_model(config)
