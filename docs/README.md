# Claude QnA Documentation

This directory contains comprehensive documentation for the Claude QnA system.

## Documentation Files

### [CQA_README.md](CQA_README.md)
Complete guide to the Claude QnA system including:
- System architecture and design
- Installation and setup instructions
- Usage examples (basic and advanced)
- Testing the sequential tool-calling hypothesis
- Comparison with the existing LangChain-based system
- Troubleshooting guide

### [MODEL_INFO.md](MODEL_INFO.md)
Model configuration reference including:
- Current Claude model details (Sonnet 4.5)
- Model history and evolution
- AWS Bedrock configuration
- Regional availability and cross-region models
- Testing procedures

## Quick Start

1. **Setup**: Follow the setup instructions in [CQA_README.md](CQA_README.md#setup)
2. **Test Connection**: Run `python scripts/test_bedrock_connection.py`
3. **Run Interactive Mode**: `python test_cqa.py`

## Additional Resources

- **Scripts Documentation**: See [../scripts/README.md](../scripts/README.md) for testing and debugging scripts
- **Main Application**: `cqa.py` (root directory)
- **Interactive Interface**: `test_cqa.py` (root directory)
