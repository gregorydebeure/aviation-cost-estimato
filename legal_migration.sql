-- Menkor — orders, proof of acceptance, legal document copies.  To run ONCE in the Supabase SQL editor (project aviation-cost-estimator).
-- Nothing is read or written by the app until LEGAL_FLOW_ENABLED=1.  Safe to re-run (IF NOT EXISTS).

create table if not exists legal_document_versions (
  sha256      text primary key,              -- fingerprint of the rendered text: the same text is stored once
  doc_key     text not null,                 -- terms | withdrawal | notice | privacy | cookies
  lang        text not null check (lang in ('fr','en')),
  version     text not null,
  effective   text,
  title       text not null,
  body        text not null,                 -- the exact text shown to the customer
  created_at  timestamptz not null default now()
);

create table if not exists orders (
  id                      text primary key,
  email                   text not null,
  customer_type           text not null check (customer_type in ('individual','business')),
  billing                 jsonb not null,
  offer_key               text not null,
  offer_label             text not null,
  amount_minor            integer not null check (amount_minor >= 0),
  currency                text not null,
  mode                    text not null check (mode in ('payment','subscription')),
  interval                text,
  category                text not null,
  status                  text not null check (status in ('draft','pending_payment','paid','failed','expired','cancelled','mismatch','refunded','partially_refunded')),
  lang                    text not null,
  terms_version           text not null,
  terms_sha256            text not null,
  extra                   jsonb not null default '{}'::jsonb,
  stripe_session_id       text unique,
  stripe_customer_id      text,
  stripe_payment_intent   text,
  stripe_subscription_id  text,
  stripe_invoice_id       text,
  paid_at                 timestamptz,
  access_start            timestamptz,
  access_end              timestamptz,
  refunded_minor          integer not null default 0,
  confirmation_sent_at    timestamptz,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now()
);
create index if not exists orders_email_idx on orders (email, created_at desc);

create table if not exists order_acceptances (
  id                     text primary key,
  order_id               text not null unique references orders(id),
  email                  text not null,
  accepted_at            timestamptz not null,         -- UTC
  lang                   text not null,
  terms_version          text not null,
  terms_sha256           text not null,
  checkbox_label         text not null,
  checkbox_label_sha256  text not null,
  documents              jsonb not null,               -- [{key, lang, version, effective, sha256}] -> legal_document_versions
  offer_snapshot         jsonb not null,               -- what was shown: offer, recap lines, price, currency, taxes, renewal, cancellation
  offer_fingerprint      text not null,
  amount_minor           integer not null,
  currency               text not null,
  mode                   text not null,
  immediate_requested    boolean not null default false,
  immediate_ack          boolean not null default false,
  immediate_label        text,
  immediate_ack_label    text,
  marketing_opt_in       boolean not null default false,   -- optional, separate, never pre-ticked
  marketing_label        text,
  retain_until           timestamptz not null              -- end of the retention period
);
create index if not exists order_acceptances_email_idx on order_acceptances (email);

create table if not exists signup_acceptances (
  id             text primary key,
  email          text not null,
  accepted_at    timestamptz not null,
  lang           text not null,
  terms_version  text not null,
  terms_sha256   text not null,
  checkbox_label text not null,
  documents      jsonb not null,
  retain_until   timestamptz not null
);
create index if not exists signup_acceptances_email_idx on signup_acceptances (email);

-- Evidence is immutable: no UPDATE ever; DELETE only once the retention period is over.
create or replace function menkor_evidence_guard() returns trigger language plpgsql as $$
begin
  if tg_op = 'UPDATE' then
    raise exception 'evidence rows are immutable (%).', tg_table_name;
  end if;
  if tg_table_name = 'legal_document_versions' then
    raise exception 'legal document copies are never deleted.';
  end if;
  if old.retain_until > now() then
    raise exception 'retention period not over for % (until %).', tg_table_name, old.retain_until;
  end if;
  return old;
end $$;

drop trigger if exists legal_document_versions_guard on legal_document_versions;
create trigger legal_document_versions_guard before update or delete on legal_document_versions for each row execute function menkor_evidence_guard();
drop trigger if exists order_acceptances_guard on order_acceptances;
create trigger order_acceptances_guard before update or delete on order_acceptances for each row execute function menkor_evidence_guard();
drop trigger if exists signup_acceptances_guard on signup_acceptances;
create trigger signup_acceptances_guard before update or delete on signup_acceptances for each row execute function menkor_evidence_guard();

-- Access: only the server (service key) reaches these tables. RLS on, no policy for anon / authenticated.
alter table legal_document_versions enable row level security;
alter table orders                  enable row level security;
alter table order_acceptances       enable row level security;
alter table signup_acceptances      enable row level security;
