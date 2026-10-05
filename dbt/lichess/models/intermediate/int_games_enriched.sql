-- Every derived field of the analysis, from the player's point of view.
-- Mirrors enrich_games / add_session_columns in notebooks/data_pipeline.py;
-- pipeline/check_parity.py compares the two implementations.
with games as (

    select * from {{ ref('stg_games') }}

),

labeled as (

    select
        g.*,
        coalesce(v.variant_name, g.variant_key)                              as variant,
        g.white_name = '{{ var("player_name") }}'                            as player_is_white,
        case g.winner
            when 'white' then '1-0'
            when 'black' then '0-1'
            else '1/2-1/2'
        end                                                                  as result,
        case g.status
            when 'outoftime' then 'Time forfeit'
            when 'timeout' then 'Abandoned'
            when 'noStart' then 'Abandoned'
            when 'cheat' then 'Rules infraction'
            else 'Normal'
        end                                                                  as termination,
        case
            when g.clock_initial is null then '-'
            else g.clock_initial || '+' || g.clock_increment
        end                                                                  as time_control,
        coalesce(
            g.tournament_name,
            case when g.is_rated then 'Rated ' else 'Casual ' end
            || case
                when g.variant_key <> 'standard' then v.variant_name
                when g.speed = 'ultraBullet' then 'UltraBullet'
                else g.speed
            end
            || ' game'
        )                                                                    as event
    from games g
    left join {{ ref('variant_names') }} v on v.variant_key = g.variant_key

),

with_player_view as (

    select
        l.*,
        case
            when l.result = '1/2-1/2' then 'draw'
            when l.player_is_white and l.result = '1-0' then 'win'
            when l.player_is_white and l.result = '0-1' then 'loss'
            when not l.player_is_white and l.result = '0-1' then 'win'
            when not l.player_is_white and l.result = '1-0' then 'loss'
        end                                                                  as result_status,
        case when l.player_is_white then 'White' else 'Black' end            as player_color,
        case when l.player_is_white then l.black_rating else l.white_rating end as opponent_elo,
        case when l.player_is_white then l.white_rating else l.black_rating end as player_elo,
        case when l.player_is_white then l.white_rating_diff else l.black_rating_diff end as player_rating_diff,
        coalesce(o.opening_name, l.eco)                                      as opening,
        cast(l.played_at as date)                                            as played_date,
        extract(hour from l.played_at)::integer                              as hour_utc
    from labeled l
    left join {{ ref('eco_openings') }} o on o.eco = l.eco

),

with_gaps as (

    select
        *,
        case
            when lag(played_at) over game_order is null then 1
            when {{ timestamp_to_ms('played_at') }}
                 - {{ timestamp_to_ms('lag(played_at) over game_order') }}
                 > {{ var('session_gap_minutes') }} * 60 * 1000 then 1
            else 0
        end                                                                  as starts_session,
        lag(result_status) over game_order                                   as previous_game_status
    from with_player_view
    window game_order as (order by played_at, game_id)

),

with_sessions as (

    select
        *,
        sum(starts_session) over (order by played_at, game_id)               as session_id
    from with_gaps

),

final as (

    select
        *,
        row_number() over (partition by session_id order by played_at, game_id) as game_in_session,
        case when starts_session = 1 then null else previous_game_status end as prev_result,
        -- pd.cut(bins=1000..3000 step 200) is right-closed: 1200 belongs to "1000-1199"
        case
            when opponent_elo > 1000 and opponent_elo <= 3000
            then cast(ceil((opponent_elo - 1000) / 200.0) as integer) - 1
        end                                                                  as elo_bin_index
    from with_sessions

)

select * from final
