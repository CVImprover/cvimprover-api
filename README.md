# CVImprover API

A Django REST API backend for AI-powered CV optimization and improvement services. The platform allows users to submit questionnaires with their career information and receive AI-generated, optimized CVs tailored to specific job applications.

## 🚀 Features

- **User Authentication & Authorization**
  - JWT-based authentication
  - Google OAuth integration
  - User profiles with subscription management

- **AI-Powered CV Generation**
  - OpenAI GPT-4 integration for CV optimization
  - PDF resume upload and text extraction
  - Questionnaire-based job targeting
  - Markdown to PDF conversion for generated CVs

- **Subscription Management**
  - Stripe integration for payments
  - Multiple subscription plans (Free, Basic, Pro, Premium)
  - Webhook handling for subscription events
  - Billing portal integration

- **Background Tasks**
  - Celery for asynchronous task processing
  - Redis as message broker and cache
  - Scheduled tasks with Celery Beat

- **API Documentation**
  - OpenAPI 3.0 schema
  - Interactive Swagger UI
  - Comprehensive endpoint documentation

## 🏗️ Tech Stack

- **Backend**: Django 5.2.1 + Django REST Framework
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery with Eventlet
- **AI**: OpenAI GPT-4
- **Payments**: Stripe
- **PDF Processing**: WeasyPrint, PyPDF2
- **Containerization**: Docker + Docker Compose
- **Deployment**: PM2, GitHub Actions

## 📋 Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL (or use Docker)
- Redis (or use Docker)
- OpenAI API key
- Stripe account (for payments)

## 🛠️ Installation

### Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cvimprover-api
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables**
   ```env
   # Django
   SECRET_KEY=your-secret-key
   DEBUG=True
   
   # Database
   DB_NAME=cvimprover
   DB_USER=postgres
   DB_PASSWORD=password
   DB_HOST=postgres_master
   DB_PORT=5432
   
   # Redis & Celery
   CELERY_BROKER_URL=redis://redis:6379/0
   CELERY_RESULT_BACKEND=redis://redis:6379/0
   CACHE_URL=redis://redis:6379/1
   
   # OpenAI
   OPENAI_API_KEY=your-openai-api-key
   
   # Stripe
   STRIPE_SECRET_KEY=your-stripe-secret-key
   STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
   STRIPE_WEBHOOK_SECRET=your-webhook-secret
   
   # Google OAuth
   GOOGLE_CLIENT_ID=your-google-client-id
   GOOGLE_CLIENT_SECRET=your-google-client-secret
   
   # CORS
   CORS_ALLOWED_ORIGINS=http://localhost:3000
   FRONTEND_URL=localhost:3000
   BACKEND_URL=localhost:8000
   ```

4. **Start the services**
   ```bash
   docker-compose up -d
   ```

5. **Run migrations and create superuser**
   ```bash
   docker-compose exec web python manage.py migrate
   docker-compose exec web python manage.py createsuperuser
   docker-compose exec web python manage.py seed_plans
   ```

### Local Development Setup

1. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up database**
   ```bash
   python manage.py migrate
   python manage.py seed_plans
   ```

4. **Start Redis and Celery**
   ```bash
   # Terminal 1: Redis
   redis-server
   
   # Terminal 2: Celery Worker
   celery -A cvimprover worker --loglevel=info
   
   # Terminal 3: Celery Beat
   celery -A cvimprover beat --loglevel=info
   ```

5. **Start Django server**
   ```bash
   python manage.py runserver
   ```


## 📄 API Pagination

All list endpoints (such as questionnaire and AI response lists) are paginated using page number pagination by default.

### How Pagination Works

- By default, each paginated endpoint returns up to 10 results per page.
- Use the `page` query parameter to navigate pages (e.g., `/cv/questionnaire/?page=2`).
- Paginated responses include the following fields:

```
{
  "count": 42,           // Total number of items
  "next": "<url>",      // URL to next page, or null
  "previous": "<url>",  // URL to previous page, or null
  "results": [ ... ]     // List of items for this page
}
```

### Example: Fetching a Paginated List

```bash
curl -H "Authorization: Bearer <your-jwt-token>" \
  http://localhost:8000/cv/questionnaire/?page=2
```

### Customizing Page Size

You can request a different page size using the `page_size` query parameter (up to a maximum allowed by the server):

```bash
curl -H "Authorization: Bearer <your-jwt-token>" \
  http://localhost:8000/cv/ai-responses/?page_size=5
```

---
## 🚦 Usage

### API Endpoints

The API provides the following main endpoints:

- **Authentication**: `/auth/`
  - User registration, login, logout
  - Google OAuth integration
  - JWT token management

- **CV Management**: `/cv/`
  - Questionnaire submission
  - AI response generation
  - PDF generation from AI responses

- **Subscription Management**: `/core/`
  - Plan listing
  - Checkout session creation
  - Billing portal access
  - Webhook handling

### Example API Usage

1. **Create a questionnaire**
   ```bash
   curl -X POST http://localhost:8000/cv/questionnaire/ \
     -H "Authorization: Bearer <your-jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "position": "Software Engineer",
       "industry": "Technology",
       "experience_level": "3-5",
       "company_size": "medium",
       "application_timeline": "1-3 months",
       "job_description": "Looking for a full-stack developer..."
     }'
   ```

2. **Generate AI response**
   ```bash
   curl -X POST http://localhost:8000/cv/ai-responses/ \
     -H "Authorization: Bearer <your-jwt-token>" \
     -H "Content-Type: application/json" \
     -d '{
       "questionnaire": 1,
       "prompt": "Please optimize my CV for this software engineering position"
     }'
   ```

## 🧪 Testing

Run the test suite:

```bash
# Using Docker
docker-compose exec web python manage.py test

# Local development
python manage.py test
```

## 📚 API Documentation

Access the interactive API documentation at:
- **Swagger UI**: `http://localhost:8000/`
- **OpenAPI Schema**: `http://localhost:8000/schema/`

## 🔧 Configuration

### Stripe Setup

1. Create a Stripe account and get your API keys
2. Set up webhook endpoint: `your-domain/core/payments/webhook/stripe/`
3. Configure subscription plans in Django admin or using the seeder

### OpenAI Setup

1. Get your OpenAI API key from the OpenAI platform
2. Add it to your environment variables
3. The system uses GPT-4 for CV optimization

### Google OAuth Setup

1. Create a Google Cloud project
2. Configure OAuth 2.0 credentials
3. Add authorized redirect URIs
4. Set the client ID and secret in environment variables

## 🚀 Deployment

### Production Deployment with PM2

The project includes PM2 configuration for production deployment:

```bash
# Start all services
pm2 start ecosystem.prod.config.js

# Monitor services
pm2 monit

# View logs
pm2 logs
```

### GitHub Actions

Automated deployment is configured via GitHub Actions:
- Tests run on pull requests
- Automatic deployment to production on main branch pushes

## 📁 Project Structure

```
cvimprover-api/
├── core/                   # Core app (users, plans, payments)
│   ├── models.py          # User and Plan models
│   ├── views.py           # Authentication and payment views
│   └── serializers.py     # API serializers
├── cv/                    # CV management app
│   ├── models.py          # Questionnaire and AI Response models
│   ├── views.py           # CV-related API endpoints
│   └── serializers.py     # CV serializers
├── cvimprover/            # Main project settings
│   ├── settings.py        # Django configuration
│   ├── urls.py           # URL routing
│   └── celery.py         # Celery configuration
├── docker-compose.yml     # Docker services configuration
├── Dockerfile            # Docker image definition
└── requirements.txt      # Python dependencies
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the GNU Affero General Public License v3.0 - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

If you encounter any issues or have questions:

1. Check the [API documentation](http://localhost:8000/)
2. Review the logs: `docker-compose logs web`
3. Open an issue on GitHub

## 🔮 Roadmap

- [ ] Additional AI model integrations
- [ ] Cover letter generation
- [ ] LinkedIn profile optimization
- [ ] Interview preparation features
- [ ] Multi-language support
- [ ] Advanced analytics dashboard

---

Built with ❤️ using Django and modern web technologies.
