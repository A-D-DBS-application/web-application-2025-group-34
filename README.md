# VEK Portfolio Management System

A comprehensive web-based portfolio management system for the VEK (Vereniging voor Economie en Krediet) student association at Ghent University.

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)

## Project Overview

This project is a **Minimum Viable Product (MVP)** designed to manage investment portfolios, transactions, voting procedures, member administration, and risk analysis for the VEK student association. The system provides a complete solution for tracking portfolio performance, managing transactions, conducting voting procedures, and analyzing investment risks.

## Core Features

### Portfolio Management
- **Position Management**: Full CRUD operations for portfolio positions with real-time price tracking
- **Live Price Updates**: Automated price synchronization via Yahoo Finance API (5-minute intervals)
- **Cash Management**: Cash balance tracking and updates
- **Company Information**: Detailed company profiles and financial ratios via Yahoo Finance integration
- **Portfolio Analytics**: Real-time portfolio value, profit/loss calculations, and position weights

### Transaction Management
- **Transaction Tracking**: Complete transaction history with full CRUD capabilities
- **Multi-Currency Support**: Support for EUR, USD, CAD, DKK with automatic exchange rate handling
- **Transaction History**: Comprehensive audit trail of all buy/sell transactions
- **Asset Classification**: Support for stocks, ETFs, bonds, crypto, and other asset classes

### Voting System
- **Proposal Management**: Create and manage voting proposals with deadlines
- **Voting Interface**: Cast votes (voor/tegen/onthouding) on proposals
- **Deadline Tracking**: Automated deadline management and enforcement
- **Real-time Results**: Live vote counting and result visualization
- **Stock-Specific Voting**: Support for stock purchase/sale voting procedures

### Risk Analysis
- **Value at Risk (VaR)**: VaR calculations at 95% and 99% confidence levels
- **Conditional VaR (CVaR)**: Expected shortfall beyond VaR threshold
- **Volatility Analysis**: Portfolio and individual position volatility metrics
- **Correlation Matrix**: Correlation analysis between portfolio positions
- **Benchmark Comparison**: Performance comparison against benchmark portfolios
- **Diversification Metrics**: Diversification scores, sector concentration, and Herfindahl-Hirschman Index
- **Sharpe Ratio**: Risk-adjusted return calculations
- **Stress Testing**: Scenario analysis with market crashes, volatility spikes, and correlation breakdowns

### Member Management
- **Role-Based Access Control**: Support for Board, Analist, Lid, and Kapitaalverschaffer roles
- **Profile Management**: User profile editing and account management
- **Member Directory**: Comprehensive member overview with role-based filtering
- **Custom ID System**: Structured member ID system encoding role, function, and year

### Dashboard & Events
- **Announcements System**: Create, update, and manage announcements
- **Event Management**: Event scheduling with iCal export functionality
- **Activity Overview**: Dashboard with recent activities and key metrics
- **Calendar Integration**: Export events to Google Calendar, Apple Calendar, Outlook

### File Management
- **Hierarchical Structure**: Folder-based file organization
- **File Upload/Download**: Secure file upload and download functionality
- **ZIP Import**: Bulk file import via ZIP archives
- **Document Organization**: Structured document management system

## Technical Architecture

### Technology Stack

**Backend Framework**
- Flask 3.1.2 - Web application framework
- SQLAlchemy 2.0.44 - ORM for database operations
- Flask-Migrate 4.1.0 - Database migration management
- Flask-Login 0.6.3 - User session management
- Flask-APScheduler 1.13.1 - Background task scheduling

**Database**
- PostgreSQL - Primary database (production)

**Frontend**
- Jinja2 3.1.6 - Template engine
- Bootstrap - Responsive CSS framework
- JavaScript - Client-side interactivity

**External APIs**
- Yahoo Finance API (yfinance 0.2.40) - Market data and company information
- Supabase 2.10.0 - Optional cloud services integration

**Data Processing**
- Pandas 2.0.0+ - Data manipulation and analysis
- NumPy 1.24.0+ - Numerical computations
- requests-cache 1.2.0+ - HTTP request caching

**Deployment**
- Gunicorn 21.2.0 - WSGI HTTP server
- Alembic 1.17.1 - Database migration tool

### Project Structure

```
Project A&D - DBS Group 34/
├── app/
│   ├── __init__.py              # Flask application factory
│   ├── models.py                # SQLAlchemy database models
│   ├── routes.py                # Route handlers and business logic
│   ├── utils.py                 # Utility functions and helpers
│   ├── jobs.py                  # Scheduled background tasks
│   ├── config.py                # Application configuration
│   ├── algorithms/
│   │   └── risk_analysis.py     # Risk analysis algorithms
│   ├── templates/               # Jinja2 HTML templates
│   │   ├── partials/           # Reusable template components
│   │   └── *.html               # Page templates
│   ├── static/                  # Static assets
│   │   ├── css/                 # Stylesheets
│   │   └── img/                 # Images
│   └── services/                # Service layer (optional)
├── migrations/                  # Alembic database migrations
│   └── versions/                # Migration version files
├── requirements.txt             # Python dependencies
├── run.py                       # Application entry point
└── README.md                    # This file
```

### Design Patterns & Architecture

**Application Factory Pattern**
- Modular Flask application initialization
- Environment-based configuration
- Extensible architecture for testing and deployment

**ORM Pattern**
- SQLAlchemy ORM for all database interactions
- No direct SQL queries in application code
- Type-safe database operations

**Blueprint Pattern**
- Organized route structure
- Separation of concerns
- Modular route registration

**Service Layer**
- Reusable business logic
- Separation of data access and presentation
- Helper functions for common operations

**Scheduled Jobs**
- Background task processing
- Automated price updates
- Time-based task execution

## Installation & Setup

### Prerequisites

- Python 3.8 or higher
- PostgreSQL database server
- Virtual environment (recommended)
- pip package manager

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd "Project A&D - DBS Group 34"
   ```

2. **Create and activate virtual environment**
   ```bash
   # Windows
   python -m venv .venv
   .venv\Scripts\activate
   
   # Linux/macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   
   Create a `.env` file or set environment variables:
   ```env
   DATABASE_URL=postgresql://username:password@localhost:5432/dbname
   SECRET_KEY=your-secret-key-here
   SUPABASE_URL=your-supabase-url  # Optional
   SUPABASE_KEY=your-supabase-key  # Optional
   ```

5. **Initialize database**
   ```bash
   # Create database migrations
   flask db upgrade
   ```

6. **Run the application**
   ```bash
   python run.py
   ```
   
   The application will be available at `http://localhost:5000`

### Database Configuration

The application uses PostgreSQL as the primary database. Connection settings are configured via the `DATABASE_URL` environment variable.

**Database Migrations**
- All schema changes are managed through Alembic migrations
- Create new migration: `flask db revision -m "description"`
- Apply migrations: `flask db upgrade`
- Rollback migration: `flask db downgrade`

## Database Schema

### Core Tables

**Members (`members`)**
- Unified table for all member types (board, analist, lid, kapitaalverschaffers)
- Role-based access control
- Custom ID system encoding role and year

**Portfolio (`portfolio`)**
- Portfolio snapshots with timestamps
- Profit/loss tracking

**Positions (`positions`)**
- Portfolio positions with real-time price data
- Current price and day change percentage
- Ticker symbols and sector information

**Transactions (`transactions`)**
- Complete transaction history
- Multi-currency support
- Asset classification and sector tracking

**Voting (`voting_proposal`, `votes`)**
- Voting proposals with deadlines
- Individual vote tracking
- Vote result calculations

**Events & Announcements (`events`, `announcements`)**
- Event management with iCal export
- Announcement system

**File Management (`file_items`)**
- Hierarchical file structure
- File metadata and organization

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | Flask secret key for sessions | Yes |
| `SUPABASE_URL` | Supabase project URL | No |
| `SUPABASE_KEY` | Supabase API key | No |

### Scheduled Jobs

The application includes automated background tasks:

- **Price Updates**: Every 5 minutes - Updates live stock prices for all positions
- Configuration: `app/__init__.py`

## Development

### Code Organization

**Best Practices**
- Helper functions organized in `routes.py` or `utils.py`
- No code duplication - reusable functions for shared logic
- Clean route handlers - business logic separated from routes
- Type safety through Enums and SQLAlchemy models

**Database Guidelines**
- Use ORM (SQLAlchemy) instead of direct SQL queries
- All schema changes through database migrations
- Enums for type safety and validation

**Template Structure**
- Reusable partials in `partials/` directory
- Base templates for consistency
- Jinja2 macros for repeated components

### Running in Development Mode

```bash
# Development server with auto-reload
python run.py

# Or using Flask CLI
flask run --debug
```

## Scalability & Performance

### Current Implementation

- **Modular Architecture**: App factory pattern for flexible deployment
- **Database Migrations**: Alembic for schema versioning
- **ORM Layer**: Type-safe database queries
- **Caching**: HTTP request caching via requests-cache
- **Background Tasks**: Scheduled jobs for automated updates
- **Code Reusability**: Helper functions and service layer

### Future Enhancements

- API endpoints for external integrations
- Real-time updates via WebSockets
- Advanced caching strategies (Redis)
- Microservices architecture (if needed)
- Horizontal scaling support

## Value-Adding Algorithm

### Risk Analysis Algorithm

The system includes a **self-implemented risk analysis algorithm** that provides:

- **Value at Risk (VaR)**: Statistical risk calculation at 95% and 99% confidence levels
- **Conditional VaR (CVaR)**: Expected shortfall beyond VaR threshold
- **Volatility Analysis**: Portfolio and position-level volatility metrics
- **Correlation Analysis**: Correlation matrix between portfolio positions
- **Diversification Metrics**: Herfindahl-Hirschman Index and diversification scores
- **Sharpe Ratio**: Risk-adjusted return calculations
- **Benchmark Comparison**: Performance comparison against benchmark portfolios

**Algorithm Implementation**:
- All core calculations (VaR, volatility, correlation, Sharpe ratio) are **implemented from scratch** by the team
- Uses standard libraries (NumPy, pandas) for mathematical operations only
- **No external black-box services** used for core functionality
- Yahoo Finance API used **exclusively for data retrieval** (historical prices)
- All feature engineering, scoring, and ranking logic implemented locally

**Correlation Calculation**:
- Correlations are calculated from historical price returns (not pre-calculated)
- Method: Pearson correlation coefficient: `corr(X,Y) = cov(X,Y) / (std(X) * std(Y))`
- Implementation: Standard statistical calculation using pandas (equivalent to manual calculation)
- Data source: Historical prices from Yahoo Finance → team calculates returns → team calculates correlations
- **No external correlation service used** - all calculations performed locally

For detailed algorithm documentation, see `app/algorithms/ALGORITHM_DOCUMENTATION.md`.

### External API Usage

**Yahoo Finance API (yfinance)**
- **Purpose**: Data retrieval only (non-core task)
- **Usage**: Historical stock prices and market data
- **Not used for**: Calculations, predictions, rankings, or classifications
- **Caching Strategy**: HTTP request caching (24-hour TTL), in-memory fallback cache, rate limiting protection

## Known Limitations (MVP Scope)

As an MVP, the following features are intentionally limited:

- Basic error handling (not production-grade)
- Limited export functionality
- No real-time notifications
- Basic analytics dashboard
- No mobile application

These limitations are by design to focus on core functionality validation.

## Partner Validation

This project was developed in collaboration with the VEK student association as an external partner.

## Team

**Group 34** - Project A&D, DBS

---

**Status**: MVP - Minimum Viable Product  
**Version**: 1.0  
**Last Updated**: January 2025
