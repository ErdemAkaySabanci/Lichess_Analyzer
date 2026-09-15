-- 02_winrate_by_opening.sql
--
-- Question: "Which openings win me the most games?"
--
-- Combines White-side and Black-side games per opening (CASE WHEN picks
-- out whichever side legend2014 played), keeps openings with at least 20
-- games for a reliable sample, and uses the RANK() window function to
-- number openings by win rate without collapsing the underlying rows.

WITH opening_totals AS (
    SELECT
        Opening,
        COUNT(*) AS games_played,
        SUM(CASE WHEN ResultStatus = 'win' THEN 1 ELSE 0 END) AS wins
    FROM games
    WHERE Event = 'Rated bullet game'
    GROUP BY Opening
    HAVING COUNT(*) >= 20
)
SELECT
    Opening,
    games_played,
    wins,
    ROUND(CAST(wins AS REAL) / games_played, 4) AS win_rate,
    RANK() OVER (ORDER BY CAST(wins AS REAL) / games_played DESC) AS win_rate_rank
FROM opening_totals
ORDER BY win_rate_rank
LIMIT 20;
