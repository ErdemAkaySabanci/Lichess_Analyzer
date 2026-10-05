-- Fact table, grain = one game. Foreign keys: played_date -> dim_date, eco -> dim_opening.
select
    game_id,
    played_at,
    played_date,
    hour_utc,
    eco,
    event,
    time_control,
    termination,
    player_color,
    result_status,
    (result_status = 'win')::integer as is_win,
    player_elo,
    opponent_elo,
    player_rating_diff,
    session_id,
    game_in_session,
    prev_result
from {{ ref('int_games_enriched') }}
