-- 06_color_ab_test.sql
--
-- Question: "Is the White-piece advantage real, or could it be chance?"
--
-- Lichess assigns colours (almost) at random, so White vs Black is the
-- closest thing in this dataset to a randomized A/B test. This query returns
-- the raw counts per time control and colour; the two-proportion z-test,
-- confidence interval and odds ratio are computed from them in
-- dashboard/stats.py (two_proportion_test).

SELECT
    Event                                                   AS time_control,
    PlayerColor,
    COUNT(*)                                                AS games_played,
    SUM(CASE WHEN ResultStatus = 'win' THEN 1 ELSE 0 END)   AS wins,
    ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate,
    ROUND(AVG(OpponentElo), 1)                              AS avg_opponent_elo
FROM games
WHERE Event IN ('Rated bullet game', 'Rated blitz game', 'Rated classical game')
GROUP BY Event, PlayerColor
ORDER BY Event, PlayerColor;
