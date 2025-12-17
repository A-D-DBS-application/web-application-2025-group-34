# VEK Portfolio Management System

A comprehensive web-based portfolio management system for the VEK student association at Ghent University.

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)

## Project Overview

This project is a **Minimum Viable Product (MVP)** designed to manage investment portfolios, transactions, voting procedures, member administration, and risk analysis for the VEK student association. The system provides a complete solution for tracking portfolio performance, managing transactions, conducting voting procedures, and analyzing investment risks.

## Links
- Figma: https://www.figma.com/make/sFxaBZzVdXEJMN3CYkF9JS/Investment-Club-MVP-Web-App?node-id=0-1&t=bmMzAAqkkwYEjWoB-1 
- Kanban: https://www.figma.com/board/CmBkSOEaXPLpsTvoq2Eno3/Kanban-group-34?node-id=6-46&t=FgQ0gUWEgC4LtVk5-0
- Render: https://vek-investment-club.onrender.com/

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

### ID-numbering

Het systeem gebruikt een gestructureerd 6-cijferig ID-systeem voor alle leden. Het ID-codeert de rol, functie/sector, en het jaar van toetreding.

**ID-structuur:**
- **Eerste cijfer (rol)**: Bepaalt het type lid
  - `0` = Board member (bestuurslid)
  - `1` = Analist
  - `2` = Lid (gewone member)
  - `3` = Kapitaalverschaffer
  - `4` = Oud-bestuur/analist (geconverteerd van origineel ID)

**Board Members (0[FUNCTIE][JAAR]):**
- Format: `0XXYYY` waarbij:
  - `XX` = Functiecode (01-06): Voorzitter, Vice-voorzitter, Penningmeester, Secretaris, etc.
  - `YYY` = Jaar suffix (laatste 3 cijfers van jaar, bijv. 2025 → 025)
- Voorbeeld: `001025` = Voorzitter uit 2025

**Analisten (1[SECTOR][NUMMER][JAAR]):**
- Format: `1XNYYY` waarbij:
  - `X` = Sectornummer (1-4): Cons. & Health, Ind., E. & R.M., etc.
  - `N` = Analist nummer binnen sector (1-9)
  - `YYY` = Jaar suffix
- Voorbeeld: `112025` = Eerste analist in sector 1 (Cons. & Health) uit 2025

**Leden (2[NUMMER][JAAR]):**
- Format: `2NNYYY` waarbij:
  - `NN` = Volgnummer binnen jaar (00-99, max 100 leden per jaar)
  - `YYY` = Jaar suffix
- Voorbeeld: `200025` = Eerste lid uit 2025

**Kapitaalverschaffers (3[NUMMER][JAAR]):**
- Format: `3NNYYY` waarbij:
  - `NN` = Volgnummer binnen jaar (00-99, max 100 per jaar)
  - `YYY` = Jaar suffix
- Voorbeeld: `300025` = Eerste kapitaalverschaffer uit 2025

**Oud-bestuur/Analisten (4[ORIGINEEL]):**
- Wanneer een board member of analist het bestuur verlaat, wordt hun ID geconverteerd:
  - Eerste cijfer wordt veranderd naar `4`
  - Rest van het ID blijft hetzelfde
- Voorbeeld: `001025` → `401025` (voormalig voorzitter uit 2025)

**Automatische ID-generatie:**
- Het systeem genereert automatisch het volgende beschikbare ID op basis van:
  - Rol van het lid
  - Functie (voor board) of sector (voor analisten)
  - Huidige jaar (of opgegeven jaar)
  - Bestaande IDs in de database
- IDs worden altijd weergegeven als 6-cijferig formaat met leading zeros (bijv. `000001`)

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

## Partner Validation

This project was developed in collaboration with the VEK student association as an external partner. The system has been validated with real-world usage scenarios and requirements from the investment club.

- Meeting 1: https://ugentbe-my.sharepoint.com/:u:/g/personal/jibbe_schiettecatte_ugent_be/IQBcNtSbAnTXQZ6TZsjDQbxVAdvO4CIRzMpmIWV1ScjPQ5U?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=va6Dcq
- Meeting 2: 
## Team

**Group 34** - Project A&D, DBS

---
