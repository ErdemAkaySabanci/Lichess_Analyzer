-- One row per game with typed columns unpacked from the raw JSON payload.
-- No business logic here: renames and casts only.
select
    id                                                       as game_id,
    {{ ms_to_timestamp('created_at') }}                      as played_at,
    try_cast({{ json_text('payload', 'rated') }} as boolean) as is_rated,
    {{ json_text('payload', 'variant') }}                    as variant_key,
    {{ json_text('payload', 'speed') }}                      as speed,
    {{ json_text('payload', 'status') }}                     as status,
    {{ json_text('payload', 'winner') }}                     as winner,
    {{ json_text('payload', 'players.white.user.name') }}    as white_name,
    {{ json_text('payload', 'players.white.user.title') }}   as white_title,
    {{ json_int('payload', 'players.white.rating') }}        as white_rating,
    {{ json_int('payload', 'players.white.ratingDiff') }}    as white_rating_diff,
    {{ json_text('payload', 'players.black.user.name') }}    as black_name,
    {{ json_text('payload', 'players.black.user.title') }}   as black_title,
    {{ json_int('payload', 'players.black.rating') }}        as black_rating,
    {{ json_int('payload', 'players.black.ratingDiff') }}    as black_rating_diff,
    {{ json_text('payload', 'opening.eco') }}                as eco,
    {{ json_int('payload', 'clock.initial') }}               as clock_initial,
    {{ json_int('payload', 'clock.increment') }}             as clock_increment,
    coalesce(
        {{ json_text('payload', 'arenaTour.name') }},
        {{ json_text('payload', 'swiss.name') }}
    )                                                        as tournament_name
from {{ source('raw', 'games') }}
