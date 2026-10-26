# Third-Party Licenses

This document contains information about third-party libraries and dependencies used in Synkora.

## Overview

Synkora uses various open-source libraries and frameworks. We are grateful to the open-source community for their contributions. Below is a summary of the main dependencies and their licenses.

## Backend Dependencies (Python/API)

### Core Framework
- **FastAPI** - MIT License - https://github.com/tiangolo/fastapi
- **Uvicorn** - BSD License - https://github.com/encode/uvicorn
- **Pydantic** - MIT License - https://github.com/pydantic/pydantic
- **SQLAlchemy** - MIT License - https://github.com/sqlalchemy/sqlalchemy
- **Alembic** - MIT License - https://github.com/sqlalchemy/alembic

### LLM & AI
- **LiteLLM** - MIT License - https://github.com/BerriAI/litellm
- **OpenAI** - MIT License - https://github.com/openai/openai-python
- **Anthropic** - MIT License - https://github.com/anthropics/anthropic-sdk-python
- **LangChain** - MIT License - https://github.com/langchain-ai/langchain
- **Cohere** - MIT License - https://github.com/cohere-ai/cohere-python

### Database & Storage
- **PostgreSQL Driver (psycopg2)** - LGPL License - https://github.com/psycopg/psycopg2
- **Redis** - BSD License - https://github.com/redis/redis-py
- **Elasticsearch** - Apache 2.0 - https://github.com/elastic/elasticsearch-py
- **Pinecone** - MIT License - https://github.com/pinecone-io/pinecone-python-client
- **Qdrant** - Apache 2.0 - https://github.com/qdrant/qdrant-client

### Security & Authentication
- **bcrypt** - Apache 2.0 - https://github.com/pyca/bcrypt
- **PyJWT** - MIT License - https://github.com/jpadilla/pyjwt
- **cryptography** - Apache 2.0/BSD - https://github.com/pyca/cryptography

### Task Queue
- **Celery** - BSD License - https://github.com/celery/celery
- **Flower** - BSD License - https://github.com/mher/flower

### HTTP & Networking
- **httpx** - BSD License - https://github.com/encode/httpx
- **requests** - Apache 2.0 - https://github.com/psf/requests
- **websockets** - BSD License - https://github.com/python-websockets/websockets

### Integrations
- **Slack SDK** - MIT License - https://github.com/slackapi/python-slack-sdk
- **Google API Client** - Apache 2.0 - https://github.com/googleapis/google-api-python-client
- **Microsoft Graph API** - MIT License - https://github.com/microsoftgraph/msgraph-sdk-python
- **Stripe** - MIT License - https://github.com/stripe/stripe-python
- **SendGrid** - MIT License - https://github.com/sendgrid/sendgrid-python

### Testing
- **pytest** - MIT License - https://github.com/pytest-dev/pytest
- **pytest-asyncio** - Apache 2.0 - https://github.com/pytest-dev/pytest-asyncio

## Frontend Dependencies (TypeScript/Next.js)

### Core Framework
- **Next.js** - MIT License - https://github.com/vercel/next.js
- **React** - MIT License - https://github.com/facebook/react
- **TypeScript** - Apache 2.0 - https://github.com/microsoft/TypeScript

### UI Components
- **Tailwind CSS** - MIT License - https://github.com/tailwindlabs/tailwindcss
- **Radix UI** - MIT License - https://github.com/radix-ui/primitives
- **Headless UI** - MIT License - https://github.com/tailwindlabs/headlessui
- **Lucide Icons** - ISC License - https://github.com/lucide-icons/lucide

### State Management & Data Fetching
- **Zustand** - MIT License - https://github.com/pmndrs/zustand
- **SWR** - MIT License - https://github.com/vercel/swr
- **Axios** - MIT License - https://github.com/axios/axios

### Forms & Validation
- **React Hook Form** - MIT License - https://github.com/react-hook-form/react-hook-form
- **Zod** - MIT License - https://github.com/colinhacks/zod

### Markdown & Code
- **React Markdown** - MIT License - https://github.com/remarkjs/react-markdown
- **React Syntax Highlighter** - MIT License - https://github.com/react-syntax-highlighter/react-syntax-highlighter

### Charts & Visualization
- **Recharts** - MIT License - https://github.com/recharts/recharts
- **Chart.js** - MIT License - https://github.com/chartjs/Chart.js

## Infrastructure & DevOps

### Containerization
- **Docker** - Apache 2.0 - https://github.com/docker/docker-ce
- **Docker Compose** - Apache 2.0 - https://github.com/docker/compose

### Orchestration
- **Kubernetes** - Apache 2.0 - https://github.com/kubernetes/kubernetes
- **Helm** - Apache 2.0 - https://github.com/helm/helm

### Databases
- **PostgreSQL** - PostgreSQL License - https://www.postgresql.org/
- **Redis** - BSD License - https://github.com/redis/redis

### Web Server
- **Nginx** - BSD License - https://github.com/nginx/nginx

## License Compliance

Synkora is distributed under the **MIT License**. All third-party dependencies use permissive licenses that are compatible with MIT distribution:

- **MIT License**: Permissive, allows commercial and non-commercial use
- **Apache 2.0 License**: Permissive, allows commercial and non-commercial use
- **BSD License**: Permissive, allows commercial and non-commercial use
- **ISC License**: Permissive, allows commercial and non-commercial use
- **LGPL License**: Used only for PostgreSQL driver (psycopg2), which is acceptable for dynamic linking
- **PostgreSQL License**: Permissive, similar to MIT/BSD

**Note**: While the third-party dependencies allow commercial use, Synkora itself requires a commercial license for commercial use. See the [LICENSE](LICENSE) file for details.

## Updating This Document

This document should be updated whenever significant dependencies are added or changed. To verify current dependencies:

```bash
# Backend dependencies
cd api && pip list

# Frontend dependencies
cd web && pnpm list
```

## Attribution

We thank all the maintainers and contributors of the above projects for their excellent work. Their efforts make Synkora possible.

### Mobile voice (Flutter)

- **sherpa-onnx** (on-device speech inference) - Apache License 2.0 - https://github.com/k2-fsa/sherpa-onnx
- **sherpa-onnx-kws-zipformer-gigaspeech-3.3M-2024-01-01** (wake-word model bundled in `flutter/synkora_mobile/assets/voice/wake`) - Apache License 2.0 - https://github.com/k2-fsa/sherpa-onnx/releases/tag/kws-models
- **record**, **just_audio**, **audio_session**, **wakelock_plus**, **shared_preferences** - BSD/MIT/Apache-2.0 - https://pub.dev

## Reporting License Issues

If you believe any dependency or license information is incorrect or missing, please:

1. Open an issue on our [GitHub repository](https://github.com/getsynkora/synkora-ai/issues)
2. Use [GitHub's private security advisory](https://github.com/getsynkora/synkora-ai/security/advisories/new) for security-related issues
3. Submit a pull request with corrections

---

*Last Updated: January 29, 2026*
