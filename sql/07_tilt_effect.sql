-- 07_tilt_effect.sql
--
-- Question: "Does the result of the previous game change how the next one goes?"
--
-- PrevResult / GameInSession come from add_session_columns() in
-- notebooks/data_pipeline.py: a session is a run of games starting within 30
-- minutes of each other, and PrevResult is empty for a session's first game.
-- This is observational (a result is not randomly assigned), and the next
-- opponent's strength differs after a win and after a loss, so the query
-- splits by opponent rating band to compare like with like. The significance
-- tests (crude and band-adjusted) live in dashboard/stats.py.

SELECT
    CASE
        WHEN OpponentElo < 2400 THEN '<2400'
        WHEN OpponentElo < 2600 THEN '2400-2599'
        WHEN OpponentElo < 2800 THEN '2600-2799'
        WHEN OpponentElo < 3000 THEN '2800-2999'
        ELSE '3000+'
    END                                                     AS elo_band,
    PrevResult,
    COUNT(*)                                                AS games_played,
    SUM(CASE WHEN ResultStatus = 'win' THEN 1 ELSE 0 END)   AS wins,
    ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate,
    ROUND(AVG(OpponentElo), 1)                              AS avg_opponent_elo,
    ROUND(AVG(GameInSession), 1)                            AS avg_game_in_session
FROM games
WHERE Event IN ('Rated bullet game', 'Rated blitz game', 'Rated classical game')
  AND PrevResult IS NOT NULL
  AND OpponentElo IS NOT NULL
GROUP BY elo_band, PrevResult
ORDER BY MIN(OpponentElo), PrevResult;
