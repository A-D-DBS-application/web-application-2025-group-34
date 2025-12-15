-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.Iv_club (
  club_id bigint NOT NULL DEFAULT nextval('"Iv_club_club_id_seq"'::regclass),
  created_at timestamp with time zone NOT NULL,
  location character varying,
  club_name character varying,
  CONSTRAINT Iv_club_pkey PRIMARY KEY (club_id)
);
CREATE TABLE public.alembic_version (
  version_num character varying NOT NULL,
  CONSTRAINT alembic_version_pkey PRIMARY KEY (version_num)
);
CREATE TABLE public.announcements (
  id bigint NOT NULL DEFAULT nextval('announcements_id_seq'::regclass),
  title character varying NOT NULL,
  body text NOT NULL,
  author character varying NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT announcements_pkey PRIMARY KEY (id)
);
CREATE TABLE public.events (
  event_number bigint NOT NULL DEFAULT nextval('events_event_number_seq'::regclass),
  event_name character varying NOT NULL,
  event_date timestamp with time zone NOT NULL,
  location character varying,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT events_pkey PRIMARY KEY (event_number)
);
CREATE TABLE public.file_items (
  item_id bigint NOT NULL DEFAULT nextval('file_items_item_id_seq'::regclass),
  name character varying NOT NULL,
  item_type character varying NOT NULL,
  parent_id bigint,
  file_path text,
  file_size bigint,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  created_by bigint,
  CONSTRAINT file_items_pkey PRIMARY KEY (item_id),
  CONSTRAINT file_items_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.members(id),
  CONSTRAINT file_items_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.file_items(item_id)
);
CREATE TABLE public.members (
  id bigint NOT NULL DEFAULT nextval('members_id_seq'::regclass),
  join_date integer NOT NULL,
  sector text,
  voting_right text,
  member_name text,
  email character varying,
  password_hash character varying,
  club_id bigint,
  guided_by uuid,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT members_pkey PRIMARY KEY (id),
  CONSTRAINT members_club_id_fkey FOREIGN KEY (club_id) REFERENCES public.Iv_club(club_id)
);
CREATE TABLE public.portfolio (
  portfolio_id bigint NOT NULL DEFAULT nextval('portfolio_portfolio_id_seq'::regclass),
  portfolio_date timestamp with time zone NOT NULL,
  profit&loss double precision,
  CONSTRAINT portfolio_pkey PRIMARY KEY (portfolio_id)
);
CREATE TABLE public.positions (
  pos_id bigint NOT NULL DEFAULT nextval('positions_pos_id_seq'::regclass),
  pos_name text NOT NULL,
  pos_type text,
  pos_quantity integer,
  portfolio_id bigint NOT NULL,
  pos_ticker character varying,
  pos_sector character varying,
  pos_value double precision,
  current_price double precision,
  day_change_pct double precision,
  CONSTRAINT positions_pkey PRIMARY KEY (pos_id),
  CONSTRAINT positions_portfolio_id_fkey FOREIGN KEY (portfolio_id) REFERENCES public.portfolio(portfolio_id)
);
CREATE TABLE public.transactions (
  transaction_id bigint NOT NULL DEFAULT nextval('transactions_transaction_id_seq'::regclass),
  transaction_date timestamp with time zone NOT NULL,
  transaction_quantity double precision,
  transaction_type text,
  sector character varying,
  asset_class character varying,
  transaction_amount double precision,
  transaction_ticker character varying,
  transaction_currency character varying,
  transaction_share_price double precision,
  asset_name text,
  asset_type text,
  CONSTRAINT transactions_pkey PRIMARY KEY (transaction_id)
);
CREATE TABLE public.votes (
  vote_id bigint NOT NULL DEFAULT nextval('votes_vote_id_seq'::regclass),
  proposal_id bigint NOT NULL,
  member_id bigint NOT NULL,
  vote_option character varying NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT votes_pkey PRIMARY KEY (vote_id),
  CONSTRAINT votes_member_id_fkey FOREIGN KEY (member_id) REFERENCES public.members(id),
  CONSTRAINT votes_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES public.voting_proposal(proposal_id)
);
CREATE TABLE public.voting_proposal (
  proposal_id bigint NOT NULL DEFAULT nextval('voting_proposal_proposal_id_seq'::regclass),
  proposal_date timestamp with time zone NOT NULL,
  proposal_type text,
  minimum_requirements text,
  stock_name character varying,
  deadline timestamp with time zone NOT NULL,
  created_at timestamp with time zone NOT NULL DEFAULT now(),
  CONSTRAINT voting_proposal_pkey PRIMARY KEY (proposal_id)
);