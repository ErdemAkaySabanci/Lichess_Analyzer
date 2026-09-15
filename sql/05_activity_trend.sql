-- 05_activity_trend.sql
--
-- Question: "How has my activity (and win rate) changed over time?"
--
-- Aggregates games per month with GROUP BY, then uses window functions
-- over the monthly series to add a 3-month moving average (smooths out
-- noisy months), a running total, and the month-over-month change via
-- LAG() -- none of these need a self-join or subquery per row.

WITH monthly AS (
    SELECT
        strftime('%Y-%m', Date) AS month,
        COUNT(*) AS games_played,
        ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
    FROM games
    WHERE Date IS NOT NULL
    GROUP BY month
)
SELECT
    month,
    games_played,
    win_rate,
    ROUND(AVG(games_played) OVER (
        ORDER BY month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 1) AS games_3mo_moving_avg,
    SUM(games_played) OVER (ORDER BY month) AS games_cumulative,
    games_played - LAG(games_played) OVER (ORDER BY month) AS games_change_vs_prev_month
FROM monthly
ORDER BY month;
