-- 03_winrate_by_elo_range.sql
--
-- Question: "Does my win rate drop against much higher-rated opponents?"
--
-- Buckets the opponent's rating into 200-point bands with CASE WHEN
-- (mirrors the pandas pd.cut bins in the notebook), then aggregates win
-- rate per band with GROUP BY.

SELECT
    CASE
        WHEN OpponentElo < 1200 THEN '<1200'
        WHEN OpponentElo < 1400 THEN '1200-1399'
        WHEN OpponentElo < 1600 THEN '1400-1599'
        WHEN OpponentElo < 1800 THEN '1600-1799'
        WHEN OpponentElo < 2000 THEN '1800-1999'
        WHEN OpponentElo < 2200 THEN '2000-2199'
        WHEN OpponentElo < 2400 THEN '2200-2399'
        WHEN OpponentElo < 2600 THEN '2400-2599'
        WHEN OpponentElo < 2800 THEN '2600-2799'
        WHEN OpponentElo < 3000 THEN '2800-2999'
        ELSE '3000+'
    END AS opponent_elo_range,
    COUNT(*) AS games_played,
    ROUND(AVG(CASE WHEN ResultStatus = 'win' THEN 1.0 ELSE 0.0 END), 4) AS win_rate
FROM games
WHERE Event = 'Rated bullet game'
  AND OpponentElo IS NOT NULL
GROUP BY opponent_elo_range
ORDER BY MIN(OpponentElo);
