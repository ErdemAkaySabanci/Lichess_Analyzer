-- 04_winrate_by_hour.sql
--
-- Question: "What time of day (UTC) do I perform best?"
--
-- Straightforward GROUP BY on the Hour column with a CASE WHEN win-rate
-- aggregate, plus a CASE WHEN bucket that labels each hour as
-- night/morning/afternoon/evening for an easier read in the dashboard.

SELECT
    Hour,
    CASE
        WHEN Hour BETWEEN 0 AND 5  THEN 'Night (00-05)'
        WHEN Hour BETWEEN 6 AND 11 THEN 'Morning (06-11)'
        WHEN Hour BETWEEN 12 AND 17 THEN 'Afternoon (12-17)'
        ELSE 'Evening (18-23)'
    END AS part_of_day,
    COUNT(*) AS games_played,
    ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
FROM games
WHERE Event = 'Rated bullet game'
GROUP BY Hour
ORDER BY Hour;
