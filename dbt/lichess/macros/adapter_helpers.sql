{#- Everything adapter-specific lives here, so the models stay plain SQL.
    Only the DuckDB implementations exist; another warehouse would need the
    same four macros written for its JSON and timestamp functions. -#}

{% macro json_text(column, path) -%}
    json_extract_string({{ column }}, '$.{{ path }}')
{%- endmacro %}

{% macro json_int(column, path) -%}
    try_cast(json_extract_string({{ column }}, '$.{{ path }}') as integer)
{%- endmacro %}

{% macro ms_to_timestamp(column) -%}
    epoch_ms({{ column }}::bigint)
{%- endmacro %}

{% macro timestamp_to_ms(column) -%}
    epoch_ms({{ column }})
{%- endmacro %}
