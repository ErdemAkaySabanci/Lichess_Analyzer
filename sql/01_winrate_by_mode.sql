-- 01_winrate_by_mode.sql
--
-- Question: "Which time control (bullet / blitz / classical) do I perform
-- best in?"
--
-- Restricts to the three rated time controls (casual games are excluded,
-- since they are not played with the same seriousness) and, for each one,
-- counts wins/losses/draws with CASE WHEN and turns them into a win rate
-- with GROUP BY + AVG.

SELECT
    Event                                              AS time_control,
    COUNT(*)                                           AS games_played,
    SUM(CASE WHEN ResultStatus = 'win'  THEN 1 ELSE 0 END) AS wins,
    SUM(CASE WHEN ResultStatus = 'loss' THEN 1 ELSE 0 END) AS losses,
    SUM(CASE WHEN ResultStatus = 'draw' THEN 1 ELSE 0 END) AS draws,
    ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
FROM games
WHERE Event IN ('Rated bullet game', 'Rated blitz game', 'Rated classical game')
GROUP BY Event
ORDER BY win_rate DESC;
