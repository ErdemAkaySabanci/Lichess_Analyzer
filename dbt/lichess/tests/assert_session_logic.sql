-- A session's first game has no previous result and every later game has one.
-- Returns the violating rows, so the test passes when it returns nothing.
select game_id, session_id, game_in_session, prev_result
from {{ ref('fct_games') }}
where (game_in_session = 1 and prev_result is not null)
   or (game_in_session > 1 and prev_result is null)
