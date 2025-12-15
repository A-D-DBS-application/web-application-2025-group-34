# VEK Portfolio Management System

A comprehensive web-based portfolio management system for the VEK student association at Ghent University.

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)

## Project Overview

This project is a **Minimum Viable Product (MVP)** designed to manage investment portfolios, transactions, voting procedures, member administration, and risk analysis for the VEK student association. The system provides a complete solution for tracking portfolio performance, managing transactions, conducting voting procedures, and analyzing investment risks.

## Links
- Figma: https://www.figma.com/make/sFxaBZzVdXEJMN3CYkF9JS/Investment-Club-MVP-Web-App?node-id=0-1&t=bmMzAAqkkwYEjWoB-1 
- Kanban: https://www.figma.com/board/CmBkSOEaXPLpsTvoq2Eno3/Kanban-group-34?node-id=6-46&t=FgQ0gUWEgC4LtVk5-0

## User Stories

| **As a <user>** | **I want to <action>** | **So that <benefit>** | **Prio** |
|-----------------|------------------------|----------------------|----------|
| User | Register & login | I can access the portfolio management system and participate in voting | 1 |
| Board Member | Create and manage portfolio positions | I can track all investments in the portfolio with real-time prices | 2 |
| Board Member | Create and manage transactions | I can record buy/sell transactions with multi-currency support | 2 |
| Board Member | Create voting proposals | Members can vote on investment decisions | 3 |
| Board Member | Manage members (create, edit, view) | I can maintain an up-to-date member directory with role-based access | 2 |
| Board Member | Create announcements | I can inform all members about important updates | 3 |
| Board Member | Create and manage events | Members can stay informed about upcoming activities | 3 |
| Board Member | View risk analysis reports | I can assess portfolio risk using VaR, CVaR, and volatility metrics | 3 |
| Analist | View portfolio positions in my sector | I can analyze investments relevant to my expertise area | 3 |
| Analist | View risk analysis for my sector | I can provide informed recommendations based on risk metrics | 3 |
| Lid (Member) | View portfolio overview | I can see the current state of our investments | 3 |
| Lid (Member) | Vote on proposals | I can participate in investment decision-making | 3 |
| Lid (Member) | View announcements | I can stay informed about club updates | 3 |
| Lid (Member) | View and export events | I can plan my schedule and add events to my calendar | 3 |
| Lid (Member) | View transaction history | I can see all buy/sell transactions that have been executed | 3 |
| Kapitaalverschaffer | View portfolio performance | I can monitor the return on my capital contribution | 3 |
| Kapitaalverschaffer | View risk analysis | I can assess the risk level of the portfolio | 3 |
| User | Upload and organize files | I can store and access important documents in a structured way | 4 |
| User | Download files | I can access stored documents when needed | 4 |
| Board Member | View member directory | I can see all members with their roles and contact information | 3 |
| User | Edit my profile | I can keep my personal information up to date | 3 |
| Board Member | View real-time portfolio analytics | I can make informed decisions based on current portfolio value and profit/loss | 2 |
| User | View diversification metrics | I can understand portfolio diversification and position relationships | 4 |

## Core Features

### Portfolio Management
- **Position Management**: Full CRUD operations for portfolio positions with real-time price tracking
- **Live Price Updates**: Automated price synchronization via Yahoo Finance API (5-minute intervals)
- **Cash Management**: Cash balance tracking and updates
- **Company Information**: Detailed company profiles and financial ratios via Yahoo Finance integration
- **Portfolio Analytics**: Real-time portfolio value, profit/loss calculations, and position weights
- **Manual Price Updates**: On-demand price refresh functionality for immediate updates

### Transaction Management
- **Transaction Tracking**: Complete transaction history with full CRUD capabilities
- **Multi-Currency Support**: Support for EUR, USD, CAD, DKK with automatic exchange rate handling
- **Transaction History**: Comprehensive audit trail of all buy/sell transactions
- **Asset Classification**: Support for stocks, ETFs, bonds, crypto, and other asset classes
- **Sector Tracking**: Automatic sector assignment for portfolio analysis

### Voting System
- **Proposal Management**: Create and manage voting proposals with deadlines
- **Voting Interface**: Cast votes (voor/tegen/onthouding) on proposals
- **Deadline Tracking**: Automated deadline management and enforcement
- **Real-time Results**: Live vote counting and result visualization
- **Stock-Specific Voting**: Support for stock purchase/sale voting procedures
- **Vote History**: Track individual member votes and proposal outcomes

### Risk Analysis
- **Value at Risk (VaR)**: VaR calculations at 95% and 99% confidence levels
- **Conditional VaR (CVaR)**: Expected shortfall beyond VaR threshold
- **Volatility Analysis**: Portfolio and individual position volatility metrics
- **Benchmark Comparison**: Performance comparison against benchmark portfolios (Defensief, Gebalanceerd, Agressief)
- **Diversification Metrics**: Diversification scores, sector concentration, and Herfindahl-Hirschman Index
- **Sharpe Ratio**: Risk-adjusted return calculations
- **Stress Testing**: Scenario analysis with market crashes, volatility spikes, and correlation breakdowns

### Member Management
- **Role-Based Access Control**: Support for Board, Analist, Lid, and Kapitaalverschaffer roles
- **Profile Management**: User profile editing and account management
- **Member Directory**: Comprehensive member overview with role-based filtering
- **Custom ID System**: Structured member ID system encoding role, function, and year
- **Member CRUD Operations**: Full create, read, update, delete functionality for board members

### Dashboard & Events
- **Announcements System**: Create, update, and manage announcements
- **Event Management**: Event scheduling with iCal export functionality
- **Activity Overview**: Dashboard with recent activities and key metrics
- **Calendar Integration**: Export events to Google Calendar, Apple Calendar, Outlook
- **Individual Event Export**: Single event iCal download
- **Bulk Event Export**: Export all events as a single calendar file

### File Management
- **Hierarchical Structure**: Folder-based file organization
- **File Upload/Download**: Secure file upload and download functionality via Supabase storage
- **ZIP Import**: Bulk file import via ZIP archives
- **Document Organization**: Structured document management system
- **File Metadata**: Track file size, creation date, and creator information

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

**External APIs & Services**
- Yahoo Finance API (yfinance 0.2.66) - Market data and company information
- Supabase 2.10.0 - Cloud storage for file management
- curl-cffi >= 0.5.10 - HTTP client for yfinance (improved compatibility)

**Data Processing**
- Pandas >= 2.0.0 - Data manipulation and analysis
- NumPy >= 1.24.0 - Numerical computations
- requests-cache >= 1.2.0 - HTTP request caching (24-hour TTL)

**Calendar & Timezone**
- icalendar 5.0.11 - iCal file generation for event exports
- pytz 2024.1 - Timezone handling (Europe/Brussels)

**Deployment**
- Gunicorn 21.2.0 - WSGI HTTP server
- Alembic 1.17.1 - Database migration tool

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
- Background task processing via Flask-APScheduler
- Automated price updates every 5 minutes
- Time-based task execution


## Database Schema

### Core Tables

**Members (`members`)**
- Unified table for all member types (board, analist, lid, kapitaalverschaffers, oud_bestuur_analisten)
- Role-based access control
- Custom ID system encoding role, function/sector, and year
- Email and password authentication
- Voting rights tracking

**Portfolio (`portfolio`)**
- Portfolio snapshots with timestamps
- Profit/loss tracking
- One-to-many relationship with positions

**Positions (`positions`)**
- Portfolio positions with real-time price data
- Current price and day change percentage (cached)
- Ticker symbols and sector information
- Quantity and value tracking
- Foreign key to portfolio

**Transactions (`transactions`)**
- Complete transaction history
- Multi-currency support (EUR, USD, CAD, DKK)
- Asset classification and sector tracking
- Transaction type (BUY/SELL)
- Share price and quantity tracking

**Voting (`voting_proposal`, `votes`)**
- Voting proposals with deadlines and stock names
- Individual vote tracking (voor/tegen/onthouding)
- Vote result calculations
- Unique constraint: one vote per member per proposal

**Events & Announcements (`events`, `announcements`)**
- Event management with iCal export
- Announcement system with author tracking
- Timestamp tracking for all entries

**File Management (`file_items`)**
- Hierarchical file structure with parent-child relationships
- File metadata (size, path, creation date)
- Creator tracking
- Support for folders and files

**Club Management (`Iv_club`)**
- Club information and location tracking
- Relationship to members

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | Flask secret key for sessions | Yes |
| `SUPABASE_URL` | Supabase project URL | No |
| `SUPABASE_KEY` | Supabase API key | No |
| `SUPABASE_BUCKET` | Supabase storage bucket name | No (default: 'files') |

### Scheduled Jobs

The application includes automated background tasks:

- **Price Updates**: Every 5 minutes - Updates live stock prices for all positions
- Configuration: `app/jobs.py` and `app/__init__.py`
- Uses requests-cache to prevent rate limiting

### File Upload Configuration

- **Max File Size**: 500MB
- **Allowed Extensions**: zip, pdf, doc, docx, xls, xlsx, txt, png, jpg, jpeg, gif
- **Storage**: Supabase cloud storage (not local filesystem)



## Scalability & Performance

### Current Implementation

- **Modular Architecture**: App factory pattern for flexible deployment
- **Database Migrations**: Alembic for schema versioning
- **ORM Layer**: Type-safe database queries
- **Caching**: HTTP request caching via requests-cache (24-hour TTL)
- **Background Tasks**: Scheduled jobs for automated updates
- **Code Reusability**: Helper functions and service layer
- **Rate Limiting Protection**: Caching prevents Yahoo Finance API rate limits


## Value-Adding Algorithm

### Risk Analysis Algorithm

The system includes a **self-implemented risk analysis algorithm** that provides:

- **Value at Risk (VaR)**: Statistical risk calculation at 95% and 99% confidence levels
- **Conditional VaR (CVaR)**: Expected shortfall beyond VaR threshold
- **Volatility Analysis**: Portfolio and position-level volatility metrics
- **Correlation Analysis**: Correlation matrix between portfolio positions
- **Diversification Metrics**: Herfindahl-Hirschman Index and diversification scores
- **Sharpe Ratio**: Risk-adjusted return calculations
- **Benchmark Comparison**: Performance comparison against benchmark portfolios (Defensief, Gebalanceerd, Agressief)
- **Stress Testing**: Scenario analysis with market crashes, volatility spikes, and correlation breakdowns

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

**Benchmark Portfolios**:
- **Defensief (ETF Mix)**: VTI (30%), VEA (25%), BND (25%), GLD (20%)
- **Gebalanceerd (Global Index)**: VTI (40%), VEA (30%), VWO (20%), BND (10%)
- **Agressief (Tech & Growth)**: QQQ (35%), VUG (25%), ARKK (20%), VTI (20%)

### External API Usage

**Yahoo Finance API (yfinance 0.2.66)**
- **Purpose**: Data retrieval only (non-core task)
- **Usage**: Historical stock prices, current prices, company information, exchange rates
- **Not used for**: Calculations, predictions, rankings, or classifications
- **Caching Strategy**: HTTP request caching (24-hour TTL), in-memory fallback cache, rate limiting protection
- **HTTP Client**: curl-cffi for improved compatibility and performance

**Supabase**
- **Purpose**: Cloud file storage
- **Usage**: Secure file upload, download, and organization
- **Not used for**: Core application logic or calculations

## Known Limitations (MVP Scope)

As an MVP, the following features are intentionally limited:

- Basic error handling (not production-grade)
- Limited export functionality
- No real-time notifications
- Basic analytics dashboard
- No mobile application
- No API documentation
- Limited user documentation

These limitations are by design to focus on core functionality validation.

## Partner Validation

This project was developed in collaboration with the VEK student association as an external partner. The system has been validated with real-world usage scenarios and requirements from the investment club.

## Team

**Group 34** - Project A&D, DBS

---
