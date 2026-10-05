-- One row per ECO code seen in the games; codes missing from the lookup seed
-- keep the code itself as their name (same fallback as the pandas pipeline).
with seen as (

    select distinct eco from {{ ref('int_games_enriched') }} where eco is not null

)

select
    seen.eco,
    coalesce(o.opening_name, seen.eco)                           as opening_name,
    trim(split_part(coalesce(o.opening_name, seen.eco), ':', 1)) as opening_family
from seen
left join {{ ref('eco_openings') }} o on o.eco = seen.eco
