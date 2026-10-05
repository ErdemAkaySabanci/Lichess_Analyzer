-- One row per calendar day with at least one game.
select distinct
    played_date                                 as date_day,
    extract(year from played_date)::integer     as year,
    extract(month from played_date)::integer    as month,
    date_trunc('month', played_date)::date      as month_start,
    dayname(played_date)                        as weekday_name,
    isodow(played_date)                         as weekday_number
from {{ ref('int_games_enriched') }}
