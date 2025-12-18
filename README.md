# VEK Portfolio Management System

A comprehensive web-based portfolio management system for the VEK student association at Ghent University.

[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/DxqGQVx4)

## Project Overview

This project is a **Minimum Viable Product (MVP)** designed to manage investment portfolios, transactions, voting procedures, member administration, and risk analysis for the VEK student association. The system provides a complete solution for tracking portfolio performance, managing transactions, conducting voting procedures, and analyzing investment risks.

## Links
- Canva: https://www.canva.com/design/DAG3EJZI7HQ/E0AwiIPxUjhldjAWlUuQTg/edit?utm_content=DAG3EJZI7HQ&utm_campaign=designshare&utm_medium=link2&utm_source=sharebutton
- Figma: https://www.figma.com/make/sFxaBZzVdXEJMN3CYkF9JS/Investment-Club-MVP-Web-App?node-id=0-1&t=bmMzAAqkkwYEjWoB-1
- Kanban: https://www.figma.com/board/CmBkSOEaXPLpsTvoq2Eno3/Kanban-group-34?node-id=6-46&t=FgQ0gUWEgC4LtVk5-0
- Render: https://vek-investment-club.onrender.com/
- Supabase: https://supabase.com/dashboard/project/reexofzxklgbyxkwaonu/database/schemas
- Demo: https://ugentbe-my.sharepoint.com/:v:/g/personal/jibbe_schiettecatte_ugent_be/IQBZvb8RgGL0Qaqk-mpQSZx-AfV1_viRYotkXEXMNDr0zVA?e=rD62m6&nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0%3D

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

The system uses a structured 6-digit ID system for all members. The ID encodes the role, function/sector, and year of joining.

**ID Structure:**
- **First digit (role)**: Determines the member type
  - `0` = Board member (bestuurslid)
  - `1` = Analist
  - `2` = Lid (regular member)
  - `3` = Kapitaalverschaffer
  - `4` = Former board/analist (converted from original ID)

**Board Members (0[FUNCTION][YEAR]):**
- Format: `0XXYYY` where:
  - `XX` = Function code (01-06): Voorzitter, Vice-voorzitter, Penningmeester, Secretaris, etc.
  - `YYY` = Year suffix (last 3 digits of year, e.g. 2025 → 025)
- Example: `001025` = Voorzitter from 2025

**Analisten (1[SECTOR][NUMBER][YEAR]):**
- Format: `1XNYYY` where:
  - `X` = Sector number (1-4): Cons. & Health, Ind., E. & R.M., etc.
  - `N` = Analist number within sector (1-9)
  - `YYY` = Year suffix
- Example: `112025` = First analist in sector 1 (Cons. & Health) from 2025

**Leden (2[NUMBER][YEAR]):**
- Format: `2NNYYY` where:
  - `NN` = Sequential number within year (00-99, max 100 members per year)
  - `YYY` = Year suffix
- Example: `200025` = First member from 2025

**Kapitaalverschaffers (3[NUMBER][YEAR]):**
- Format: `3NNYYY` where:
  - `NN` = Sequential number within year (00-99, max 100 per year)
  - `YYY` = Year suffix
- Example: `300025` = First kapitaalverschaffer from 2025

**Former Board/Analisten (4[ORIGINAL]):**
- When a board member or analist leaves the board, their ID is converted:
  - First digit is changed to `4`
  - Rest of the ID remains the same
- Example: `001025` → `401025` (former voorzitter from 2025)

**Automatic ID Generation:**
- The system automatically generates the next available ID based on:
  - Member role
  - Function (for board) or sector (for analisten)
  - Current year (or specified year)
  - Existing IDs in the database
- IDs are always displayed as 6-digit format with leading zeros (e.g. `000001`)


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

### Authentication & Passwords

For development and testing purposes, passwords for all members can be found in the `Database Dumb/passwords.csv` file. The passwords in this CSV file are stored in plain text format for easy access during development. However, in the actual database, all passwords are stored in hashed format using secure password hashing algorithms. This ensures that passwords are never stored in plain text in the production database, providing security even if the database is compromised.

**Important Notes:**
- The CSV file contains plain text passwords for development/testing only
- Database passwords are hashed and cannot be reversed
- Never commit the passwords.csv file to version control in a production environment
- Use the CSV file only for local development and testing

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

- Meeting 1: https://ugentbe-my.sharepoint.com/:u:/g/personal/nicholas_vandekerckhove_ugent_be/IQDaWfIPXYB7SoAEu1DczC_JAQ1nfQqsi--7cLxK579EwgU?e=5vidD8&nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJTdHJlYW1XZWJBcHAiLCJyZWZlcnJhbFZpZXciOiJTaGFyZURpYWxvZy1MaW5rIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXcifX0%3D

- Meeting 2: https://ugentbe-my.sharepoint.com/:u:/g/personal/jibbe_schiettecatte_ugent_be/IQBcNtSbAnTXQZ6TZsjDQbxVAdvO4CIRzMpmIWV1ScjPQ5U?nav=eyJyZWZlcnJhbEluZm8iOnsicmVmZXJyYWxBcHAiOiJPbmVEcml2ZUZvckJ1c2luZXNzIiwicmVmZXJyYWxBcHBQbGF0Zm9ybSI6IldlYiIsInJlZmVycmFsTW9kZSI6InZpZXciLCJyZWZlcnJhbFZpZXciOiJNeUZpbGVzTGlua0NvcHkifX0&e=va6Dcq

## Team

**Group 34** - Project A&D, DBS

---
