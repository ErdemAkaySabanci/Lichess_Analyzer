-- Wide, one-row-per-game table with exactly the columns of
-- data/processed/lichess_games_clean.csv (plus GameId), so the existing SQL
-- files and dashboard queries run against it unchanged.
select
    event                                       as "Event",
    white_name                                  as "White",
    black_name                                  as "Black",
    result                                      as "Result",
    strftime(played_at, '%Y.%m.%d')             as "UTCDate",
    strftime(played_at, '%H:%M:%S')             as "UTCTime",
    white_rating                                as "WhiteElo",
    black_rating                                as "BlackElo",
    white_rating_diff                           as "WhiteRatingDiff",
    black_rating_diff                           as "BlackRatingDiff",
    white_title                                 as "WhiteTitle",
    black_title                                 as "BlackTitle",
    variant                                     as "Variant",
    time_control                                as "TimeControl",
    eco                                         as "ECO",
    termination                                 as "Termination",
    result_status                               as "ResultStatus",
    strftime(played_at, '%Y-%m-%d')             as "Date",
    hour_utc                                    as "Hour",
    opening                                     as "Opening",
    event in ('Rated bullet game', 'Rated blitz game', 'Rated classical game') as "IsRanked",
    opponent_elo                                as "OpponentElo",
    case
        when elo_bin_index is not null
        then (1000 + 200 * elo_bin_index) || '-' || (1000 + 200 * elo_bin_index + 199)
    end                                         as "OpponentEloRange",
    player_color                                as "PlayerColor",
    session_id                                  as "SessionId",
    game_in_session                             as "GameInSession",
    prev_result                                 as "PrevResult",
    game_id                                     as "GameId"
from {{ ref('int_games_enriched') }}
order by played_at desc, game_id desc
