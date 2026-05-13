{% macro audit_columns() %}
    CURRENT_TIMESTAMP() AS dbt_loaded_at,
    '{{ invocation_id }}' AS dbt_invocation_id
{% endmacro %}