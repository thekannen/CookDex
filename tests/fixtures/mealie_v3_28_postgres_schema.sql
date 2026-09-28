-- Mealie v3.28.0 PostgreSQL schema (pg_dump --schema-only), for CookDex's
-- direct-database integration tests. Structure only; no data.
--
-- PostgreSQL database dump
--


-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pg_trgm; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public;


--
-- Name: EXTENSION pg_trgm; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pg_trgm IS 'text similarity measurement and index searching based on trigrams';


--
-- Name: authmethod; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.authmethod AS ENUM (
    'MEALIE',
    'LDAP',
    'OIDC'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: ai_provider_headers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_provider_headers (
    provider_id uuid NOT NULL,
    id integer NOT NULL,
    key_name character varying,
    value character varying,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: ai_provider_headers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_provider_headers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_provider_headers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_provider_headers_id_seq OWNED BY public.ai_provider_headers.id;


--
-- Name: ai_provider_params; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_provider_params (
    provider_id uuid NOT NULL,
    id integer NOT NULL,
    key_name character varying,
    value character varying,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: ai_provider_params_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ai_provider_params_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ai_provider_params_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ai_provider_params_id_seq OWNED BY public.ai_provider_params.id;


--
-- Name: ai_provider_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_provider_settings (
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    default_provider_id uuid,
    audio_provider_id uuid,
    image_provider_id uuid,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: ai_providers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ai_providers (
    id uuid NOT NULL,
    settings_id uuid NOT NULL,
    name character varying NOT NULL,
    base_url character varying,
    api_key character varying NOT NULL,
    model character varying NOT NULL,
    timeout integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


--
-- Name: api_extras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_extras (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    recipee_id uuid,
    key_name character varying,
    value character varying
);


--
-- Name: api_extras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.api_extras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_extras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_extras_id_seq OWNED BY public.api_extras.id;


--
-- Name: categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.categories (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    group_id uuid NOT NULL,
    id uuid NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL
);


--
-- Name: cookbooks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cookbooks (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    "position" integer NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL,
    description character varying,
    group_id uuid,
    public boolean,
    require_all_categories boolean,
    require_all_tags boolean,
    require_all_tools boolean,
    household_id uuid,
    query_filter_string character varying DEFAULT ''::character varying NOT NULL
);


--
-- Name: cookbooks_to_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cookbooks_to_categories (
    cookbook_id uuid,
    category_id uuid
);


--
-- Name: cookbooks_to_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cookbooks_to_tags (
    cookbook_id uuid,
    tag_id uuid
);


--
-- Name: cookbooks_to_tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.cookbooks_to_tools (
    cookbook_id uuid,
    tool_id uuid
);


--
-- Name: group_data_exports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_data_exports (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid,
    name character varying NOT NULL,
    filename character varying NOT NULL,
    path character varying NOT NULL,
    size character varying NOT NULL,
    expires character varying NOT NULL
);


--
-- Name: group_events_notifier_options; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_events_notifier_options (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    event_notifier_id uuid NOT NULL,
    recipe_created boolean NOT NULL,
    recipe_updated boolean NOT NULL,
    recipe_deleted boolean NOT NULL,
    user_signup boolean NOT NULL,
    data_migrations boolean NOT NULL,
    data_export boolean NOT NULL,
    data_import boolean NOT NULL,
    mealplan_entry_created boolean NOT NULL,
    shopping_list_created boolean NOT NULL,
    shopping_list_updated boolean NOT NULL,
    shopping_list_deleted boolean NOT NULL,
    cookbook_created boolean NOT NULL,
    cookbook_updated boolean NOT NULL,
    cookbook_deleted boolean NOT NULL,
    tag_created boolean NOT NULL,
    tag_updated boolean NOT NULL,
    tag_deleted boolean NOT NULL,
    category_created boolean NOT NULL,
    category_updated boolean NOT NULL,
    category_deleted boolean NOT NULL,
    label_created boolean DEFAULT false NOT NULL,
    label_updated boolean DEFAULT false NOT NULL,
    label_deleted boolean DEFAULT false NOT NULL,
    mealplan_entry_updated boolean DEFAULT false NOT NULL,
    mealplan_entry_deleted boolean DEFAULT false NOT NULL
);


--
-- Name: group_events_notifiers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_events_notifiers (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    name character varying NOT NULL,
    enabled boolean NOT NULL,
    apprise_url character varying NOT NULL,
    group_id uuid,
    household_id uuid
);


--
-- Name: group_meal_plan_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_meal_plan_rules (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    day character varying NOT NULL,
    entry_type character varying NOT NULL,
    household_id uuid,
    query_filter_string character varying DEFAULT ''::character varying NOT NULL
);


--
-- Name: group_meal_plans; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_meal_plans (
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    date date NOT NULL,
    entry_type character varying NOT NULL,
    title character varying NOT NULL,
    text character varying NOT NULL,
    group_id uuid,
    recipe_id uuid,
    user_id uuid
);


--
-- Name: group_meal_plans_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.group_meal_plans_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: group_meal_plans_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.group_meal_plans_id_seq OWNED BY public.group_meal_plans.id;


--
-- Name: group_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_preferences (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    private_group boolean,
    first_day_of_week integer,
    recipe_public boolean,
    recipe_show_nutrition boolean,
    recipe_show_assets boolean,
    recipe_landscape_view boolean,
    recipe_disable_comments boolean,
    recipe_disable_amount boolean,
    show_announcements boolean DEFAULT true NOT NULL
);


--
-- Name: group_reports; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_reports (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    name character varying NOT NULL,
    status character varying NOT NULL,
    category character varying NOT NULL,
    "timestamp" timestamp without time zone NOT NULL,
    group_id uuid NOT NULL
);


--
-- Name: group_to_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.group_to_categories (
    group_id uuid,
    category_id uuid
);


--
-- Name: groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.groups (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    name character varying NOT NULL,
    slug character varying
);


--
-- Name: household_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.household_preferences (
    id uuid NOT NULL,
    household_id uuid NOT NULL,
    private_household boolean,
    first_day_of_week integer,
    recipe_public boolean,
    recipe_show_nutrition boolean,
    recipe_show_assets boolean,
    recipe_landscape_view boolean,
    recipe_disable_comments boolean,
    recipe_disable_amount boolean,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    lock_recipe_edits_from_other_households boolean,
    show_announcements boolean DEFAULT true NOT NULL
);


--
-- Name: households; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.households (
    id uuid NOT NULL,
    name character varying NOT NULL,
    slug character varying,
    group_id uuid NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: households_to_ingredient_foods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.households_to_ingredient_foods (
    household_id uuid,
    food_id uuid
);


--
-- Name: households_to_recipes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.households_to_recipes (
    id uuid NOT NULL,
    household_id uuid NOT NULL,
    recipe_id uuid NOT NULL,
    last_made timestamp without time zone,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: households_to_tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.households_to_tools (
    household_id uuid,
    tool_id uuid
);


--
-- Name: ingredient_food_extras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredient_food_extras (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    key_name character varying,
    value character varying,
    ingredient_food_id uuid
);


--
-- Name: ingredient_food_extras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.ingredient_food_extras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: ingredient_food_extras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.ingredient_food_extras_id_seq OWNED BY public.ingredient_food_extras.id;


--
-- Name: ingredient_foods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredient_foods (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    name character varying,
    description character varying,
    label_id uuid,
    name_normalized character varying,
    plural_name character varying,
    plural_name_normalized character varying,
    on_hand boolean NOT NULL
);


--
-- Name: ingredient_foods_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredient_foods_aliases (
    id uuid NOT NULL,
    food_id uuid NOT NULL,
    name character varying NOT NULL,
    name_normalized character varying,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: ingredient_foods_substitutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredient_foods_substitutions (
    id uuid NOT NULL,
    food_id uuid NOT NULL,
    substitute_food_id uuid,
    note character varying,
    "position" integer,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    CONSTRAINT ingredient_foods_substitutions_food_or_note CHECK (((substitute_food_id IS NOT NULL) OR (note IS NOT NULL))),
    CONSTRAINT ingredient_foods_substitutions_no_self_substitution CHECK ((food_id <> substitute_food_id))
);


--
-- Name: ingredient_units; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredient_units (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    name character varying,
    description character varying,
    abbreviation character varying,
    fraction boolean,
    use_abbreviation boolean,
    name_normalized character varying,
    abbreviation_normalized character varying,
    plural_name character varying,
    plural_name_normalized character varying,
    plural_abbreviation character varying,
    plural_abbreviation_normalized character varying,
    standard_quantity double precision,
    standard_unit character varying
);


--
-- Name: ingredient_units_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.ingredient_units_aliases (
    id uuid NOT NULL,
    unit_id uuid NOT NULL,
    name character varying NOT NULL,
    name_normalized character varying,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: invite_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.invite_tokens (
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    token character varying NOT NULL,
    uses_left integer NOT NULL,
    group_id uuid,
    household_id uuid
);


--
-- Name: invite_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.invite_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: invite_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.invite_tokens_id_seq OWNED BY public.invite_tokens.id;


--
-- Name: long_live_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.long_live_tokens (
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    name character varying NOT NULL,
    token character varying NOT NULL,
    user_id uuid
);


--
-- Name: long_live_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.long_live_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: long_live_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.long_live_tokens_id_seq OWNED BY public.long_live_tokens.id;


--
-- Name: multi_purpose_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.multi_purpose_labels (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    color character varying(10) NOT NULL,
    group_id uuid NOT NULL
);


--
-- Name: notes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notes (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    recipe_id uuid,
    title character varying,
    text character varying,
    reference_id uuid
);


--
-- Name: notes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notes_id_seq OWNED BY public.notes.id;


--
-- Name: password_reset_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.password_reset_tokens (
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    user_id uuid NOT NULL,
    token character varying(64) NOT NULL
);


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.password_reset_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: password_reset_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.password_reset_tokens_id_seq OWNED BY public.password_reset_tokens.id;


--
-- Name: plan_rules_to_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plan_rules_to_categories (
    group_plan_rule_id uuid,
    category_id uuid
);


--
-- Name: plan_rules_to_households; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plan_rules_to_households (
    group_plan_rule_id uuid,
    household_id uuid
);


--
-- Name: plan_rules_to_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.plan_rules_to_tags (
    plan_rule_id uuid,
    tag_id uuid
);


--
-- Name: recipe_actions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_actions (
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    action_type character varying NOT NULL,
    title character varying NOT NULL,
    url character varying NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    household_id uuid
);


--
-- Name: recipe_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_assets (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    recipe_id uuid,
    name character varying,
    icon character varying,
    file_name character varying
);


--
-- Name: recipe_assets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipe_assets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipe_assets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipe_assets_id_seq OWNED BY public.recipe_assets.id;


--
-- Name: recipe_comments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_comments (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    text character varying,
    recipe_id uuid NOT NULL,
    user_id uuid NOT NULL
);


--
-- Name: recipe_ingredient_ref_link; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_ingredient_ref_link (
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    instruction_id uuid,
    reference_id uuid
);


--
-- Name: recipe_ingredient_ref_link_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipe_ingredient_ref_link_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipe_ingredient_ref_link_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipe_ingredient_ref_link_id_seq OWNED BY public.recipe_ingredient_ref_link.id;


--
-- Name: recipe_instructions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_instructions (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    recipe_id uuid,
    "position" integer,
    type character varying,
    title character varying,
    text character varying,
    summary character varying
);


--
-- Name: recipe_note_ref_link; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_note_ref_link (
    instruction_id uuid,
    reference_id uuid,
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: recipe_note_ref_link_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipe_note_ref_link_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipe_note_ref_link_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipe_note_ref_link_id_seq OWNED BY public.recipe_note_ref_link.id;


--
-- Name: recipe_nutrition; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_nutrition (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    recipe_id uuid,
    calories character varying,
    fat_content character varying,
    fiber_content character varying,
    protein_content character varying,
    carbohydrate_content character varying,
    sodium_content character varying,
    sugar_content character varying,
    cholesterol_content character varying,
    saturated_fat_content character varying,
    trans_fat_content character varying,
    unsaturated_fat_content character varying
);


--
-- Name: recipe_nutrition_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipe_nutrition_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipe_nutrition_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipe_nutrition_id_seq OWNED BY public.recipe_nutrition.id;


--
-- Name: recipe_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_settings (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    recipe_id uuid,
    public boolean,
    show_nutrition boolean,
    show_assets boolean,
    landscape_view boolean,
    disable_amount boolean,
    disable_comments boolean,
    locked boolean
);


--
-- Name: recipe_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipe_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipe_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipe_settings_id_seq OWNED BY public.recipe_settings.id;


--
-- Name: recipe_share_tokens; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_share_tokens (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    recipe_id uuid NOT NULL,
    expires_at timestamp without time zone NOT NULL
);


--
-- Name: recipe_timeline_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipe_timeline_events (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    recipe_id uuid NOT NULL,
    user_id uuid NOT NULL,
    subject character varying NOT NULL,
    message character varying,
    event_type character varying,
    image character varying,
    "timestamp" timestamp without time zone
);


--
-- Name: recipes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipes (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    slug character varying,
    group_id uuid NOT NULL,
    user_id uuid,
    name character varying NOT NULL,
    description character varying,
    image character varying,
    total_time character varying,
    prep_time character varying,
    perform_time character varying,
    cook_time character varying,
    recipe_yield character varying,
    "recipeCuisine" character varying,
    rating double precision,
    org_url character varying,
    date_added date,
    date_updated timestamp without time zone,
    is_ocr_recipe boolean,
    last_made timestamp without time zone,
    name_normalized character varying NOT NULL,
    description_normalized character varying,
    recipe_yield_quantity double precision DEFAULT '0'::double precision NOT NULL,
    recipe_servings double precision DEFAULT '0'::double precision NOT NULL
);


--
-- Name: recipes_ingredients; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipes_ingredients (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    "position" integer,
    recipe_id uuid,
    title character varying,
    note character varying,
    unit_id uuid,
    food_id uuid,
    quantity double precision,
    reference_id uuid,
    original_text character varying,
    note_normalized character varying,
    original_text_normalized character varying,
    referenced_recipe_id uuid
);


--
-- Name: recipes_ingredients_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.recipes_ingredients_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: recipes_ingredients_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.recipes_ingredients_id_seq OWNED BY public.recipes_ingredients.id;


--
-- Name: recipes_ingredients_substitutions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipes_ingredients_substitutions (
    id uuid NOT NULL,
    ingredient_id integer NOT NULL,
    substitute_food_id uuid,
    note character varying,
    "position" integer,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    CONSTRAINT recipes_ingredients_substitutions_food_or_note CHECK (((substitute_food_id IS NOT NULL) OR (note IS NOT NULL)))
);


--
-- Name: recipes_to_categories; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipes_to_categories (
    recipe_id uuid,
    category_id uuid
);


--
-- Name: recipes_to_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipes_to_tags (
    recipe_id uuid,
    tag_id uuid
);


--
-- Name: recipes_to_tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.recipes_to_tools (
    recipe_id uuid,
    tool_id uuid
);


--
-- Name: report_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.report_entries (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    success boolean,
    message character varying,
    exception character varying,
    "timestamp" timestamp without time zone NOT NULL,
    report_id uuid NOT NULL
);


--
-- Name: server_tasks; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.server_tasks (
    id integer NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    name character varying NOT NULL,
    completed_date timestamp without time zone,
    status character varying NOT NULL,
    log character varying,
    group_id uuid NOT NULL
);


--
-- Name: server_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.server_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: server_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.server_tasks_id_seq OWNED BY public.server_tasks.id;


--
-- Name: shopping_list_extras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_list_extras (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    key_name character varying,
    value character varying,
    shopping_list_id uuid
);


--
-- Name: shopping_list_extras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.shopping_list_extras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: shopping_list_extras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.shopping_list_extras_id_seq OWNED BY public.shopping_list_extras.id;


--
-- Name: shopping_list_item_extras; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_list_item_extras (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id integer NOT NULL,
    key_name character varying,
    value character varying,
    shopping_list_item_id uuid
);


--
-- Name: shopping_list_item_extras_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.shopping_list_item_extras_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: shopping_list_item_extras_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.shopping_list_item_extras_id_seq OWNED BY public.shopping_list_item_extras.id;


--
-- Name: shopping_list_item_recipe_reference; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_list_item_recipe_reference (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    shopping_list_item_id uuid NOT NULL,
    recipe_id uuid,
    recipe_quantity double precision NOT NULL,
    recipe_scale double precision NOT NULL,
    recipe_note character varying
);


--
-- Name: shopping_list_items; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_list_items (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    shopping_list_id uuid,
    is_ingredient boolean,
    "position" integer NOT NULL,
    checked boolean,
    quantity double precision,
    note character varying,
    is_food boolean,
    unit_id uuid,
    food_id uuid,
    label_id uuid
);


--
-- Name: shopping_list_recipe_reference; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_list_recipe_reference (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    shopping_list_id uuid NOT NULL,
    recipe_id uuid,
    recipe_quantity double precision NOT NULL
);


--
-- Name: shopping_lists; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_lists (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    name character varying,
    user_id uuid NOT NULL
);


--
-- Name: shopping_lists_multi_purpose_labels; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.shopping_lists_multi_purpose_labels (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    shopping_list_id uuid NOT NULL,
    label_id uuid NOT NULL,
    "position" integer NOT NULL
);


--
-- Name: tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tags (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL
);


--
-- Name: tools; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tools (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid NOT NULL,
    name character varying NOT NULL,
    slug character varying NOT NULL,
    on_hand boolean
);


--
-- Name: users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    full_name character varying,
    username character varying,
    email character varying,
    password character varying,
    admin boolean,
    advanced boolean,
    group_id uuid NOT NULL,
    cache_key character varying,
    can_manage boolean,
    can_invite boolean,
    can_organize boolean,
    owned_recipes_id uuid,
    login_attemps integer,
    locked_at timestamp without time zone,
    auth_method public.authmethod DEFAULT 'MEALIE'::public.authmethod NOT NULL,
    household_id uuid,
    can_manage_household boolean,
    show_announcements boolean DEFAULT true NOT NULL,
    last_read_announcement character varying,
    tokens_valid_after timestamp without time zone,
    external_avatar_hash character varying
);


--
-- Name: users_to_recipes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.users_to_recipes (
    user_id uuid NOT NULL,
    recipe_id uuid NOT NULL,
    rating double precision,
    is_favorite boolean NOT NULL,
    id uuid NOT NULL,
    created_at timestamp without time zone,
    update_at timestamp without time zone
);


--
-- Name: webhook_urls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.webhook_urls (
    created_at timestamp without time zone,
    update_at timestamp without time zone,
    id uuid NOT NULL,
    group_id uuid,
    enabled boolean,
    name character varying,
    url character varying,
    "time" character varying,
    webhook_type character varying,
    scheduled_time time without time zone,
    household_id uuid
);


--
-- Name: ai_provider_headers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_headers ALTER COLUMN id SET DEFAULT nextval('public.ai_provider_headers_id_seq'::regclass);


--
-- Name: ai_provider_params id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_params ALTER COLUMN id SET DEFAULT nextval('public.ai_provider_params_id_seq'::regclass);


--
-- Name: api_extras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_extras ALTER COLUMN id SET DEFAULT nextval('public.api_extras_id_seq'::regclass);


--
-- Name: group_meal_plans id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plans ALTER COLUMN id SET DEFAULT nextval('public.group_meal_plans_id_seq'::regclass);


--
-- Name: ingredient_food_extras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_food_extras ALTER COLUMN id SET DEFAULT nextval('public.ingredient_food_extras_id_seq'::regclass);


--
-- Name: invite_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_tokens ALTER COLUMN id SET DEFAULT nextval('public.invite_tokens_id_seq'::regclass);


--
-- Name: long_live_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.long_live_tokens ALTER COLUMN id SET DEFAULT nextval('public.long_live_tokens_id_seq'::regclass);


--
-- Name: notes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes ALTER COLUMN id SET DEFAULT nextval('public.notes_id_seq'::regclass);


--
-- Name: password_reset_tokens id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens ALTER COLUMN id SET DEFAULT nextval('public.password_reset_tokens_id_seq'::regclass);


--
-- Name: recipe_assets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_assets ALTER COLUMN id SET DEFAULT nextval('public.recipe_assets_id_seq'::regclass);


--
-- Name: recipe_ingredient_ref_link id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredient_ref_link ALTER COLUMN id SET DEFAULT nextval('public.recipe_ingredient_ref_link_id_seq'::regclass);


--
-- Name: recipe_note_ref_link id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_note_ref_link ALTER COLUMN id SET DEFAULT nextval('public.recipe_note_ref_link_id_seq'::regclass);


--
-- Name: recipe_nutrition id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_nutrition ALTER COLUMN id SET DEFAULT nextval('public.recipe_nutrition_id_seq'::regclass);


--
-- Name: recipe_settings id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_settings ALTER COLUMN id SET DEFAULT nextval('public.recipe_settings_id_seq'::regclass);


--
-- Name: recipes_ingredients id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients ALTER COLUMN id SET DEFAULT nextval('public.recipes_ingredients_id_seq'::regclass);


--
-- Name: server_tasks id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.server_tasks ALTER COLUMN id SET DEFAULT nextval('public.server_tasks_id_seq'::regclass);


--
-- Name: shopping_list_extras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_extras ALTER COLUMN id SET DEFAULT nextval('public.shopping_list_extras_id_seq'::regclass);


--
-- Name: shopping_list_item_extras id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_item_extras ALTER COLUMN id SET DEFAULT nextval('public.shopping_list_item_extras_id_seq'::regclass);


--
-- Name: ai_provider_headers ai_provider_headers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_headers
    ADD CONSTRAINT ai_provider_headers_pkey PRIMARY KEY (id);


--
-- Name: ai_provider_params ai_provider_params_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_params
    ADD CONSTRAINT ai_provider_params_pkey PRIMARY KEY (id);


--
-- Name: ai_provider_settings ai_provider_settings_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_settings
    ADD CONSTRAINT ai_provider_settings_group_id_key UNIQUE (group_id);


--
-- Name: ai_provider_settings ai_provider_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_settings
    ADD CONSTRAINT ai_provider_settings_pkey PRIMARY KEY (id);


--
-- Name: ai_providers ai_providers_name_settings_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_providers
    ADD CONSTRAINT ai_providers_name_settings_id_key UNIQUE (name, settings_id);


--
-- Name: ai_providers ai_providers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_providers
    ADD CONSTRAINT ai_providers_pkey PRIMARY KEY (id);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: api_extras api_extras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_extras
    ADD CONSTRAINT api_extras_pkey PRIMARY KEY (id);


--
-- Name: categories categories_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_pkey PRIMARY KEY (id);


--
-- Name: categories category_slug_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT category_slug_group_id_key UNIQUE (slug, group_id);


--
-- Name: cookbooks_to_categories cookbook_id_category_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_categories
    ADD CONSTRAINT cookbook_id_category_id_key UNIQUE (cookbook_id, category_id);


--
-- Name: cookbooks_to_tags cookbook_id_tag_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_tags
    ADD CONSTRAINT cookbook_id_tag_id_key UNIQUE (cookbook_id, tag_id);


--
-- Name: cookbooks_to_tools cookbook_id_tool_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_tools
    ADD CONSTRAINT cookbook_id_tool_id_key UNIQUE (cookbook_id, tool_id);


--
-- Name: cookbooks cookbook_slug_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks
    ADD CONSTRAINT cookbook_slug_group_id_key UNIQUE (slug, group_id);


--
-- Name: cookbooks cookbooks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks
    ADD CONSTRAINT cookbooks_pkey PRIMARY KEY (id);


--
-- Name: group_data_exports group_data_exports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_data_exports
    ADD CONSTRAINT group_data_exports_pkey PRIMARY KEY (id);


--
-- Name: group_events_notifier_options group_events_notifier_options_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_events_notifier_options
    ADD CONSTRAINT group_events_notifier_options_pkey PRIMARY KEY (id);


--
-- Name: group_events_notifiers group_events_notifiers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_events_notifiers
    ADD CONSTRAINT group_events_notifiers_pkey PRIMARY KEY (id);


--
-- Name: group_to_categories group_id_category_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_to_categories
    ADD CONSTRAINT group_id_category_id_key UNIQUE (group_id, category_id);


--
-- Name: group_meal_plan_rules group_meal_plan_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plan_rules
    ADD CONSTRAINT group_meal_plan_rules_pkey PRIMARY KEY (id);


--
-- Name: group_meal_plans group_meal_plans_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plans
    ADD CONSTRAINT group_meal_plans_pkey PRIMARY KEY (id);


--
-- Name: plan_rules_to_categories group_plan_rule_id_category_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_categories
    ADD CONSTRAINT group_plan_rule_id_category_id_key UNIQUE (group_plan_rule_id, category_id);


--
-- Name: plan_rules_to_households group_plan_rule_id_household_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_households
    ADD CONSTRAINT group_plan_rule_id_household_id_key UNIQUE (group_plan_rule_id, household_id);


--
-- Name: group_preferences group_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_preferences
    ADD CONSTRAINT group_preferences_pkey PRIMARY KEY (id);


--
-- Name: group_reports group_reports_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_reports
    ADD CONSTRAINT group_reports_pkey PRIMARY KEY (id);


--
-- Name: groups groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.groups
    ADD CONSTRAINT groups_pkey PRIMARY KEY (id);


--
-- Name: households_to_ingredient_foods household_id_food_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_ingredient_foods
    ADD CONSTRAINT household_id_food_id_key UNIQUE (household_id, food_id);


--
-- Name: households_to_recipes household_id_recipe_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_recipes
    ADD CONSTRAINT household_id_recipe_id_key UNIQUE (household_id, recipe_id);


--
-- Name: households_to_tools household_id_tool_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_tools
    ADD CONSTRAINT household_id_tool_id_key UNIQUE (household_id, tool_id);


--
-- Name: households household_name_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT household_name_group_id_key UNIQUE (group_id, name);


--
-- Name: household_preferences household_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.household_preferences
    ADD CONSTRAINT household_preferences_pkey PRIMARY KEY (id);


--
-- Name: households household_slug_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT household_slug_group_id_key UNIQUE (group_id, slug);


--
-- Name: households households_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT households_pkey PRIMARY KEY (id);


--
-- Name: households_to_recipes households_to_recipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_recipes
    ADD CONSTRAINT households_to_recipes_pkey PRIMARY KEY (id, household_id, recipe_id);


--
-- Name: ingredient_food_extras ingredient_food_extras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_food_extras
    ADD CONSTRAINT ingredient_food_extras_pkey PRIMARY KEY (id);


--
-- Name: ingredient_foods_aliases ingredient_foods_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods_aliases
    ADD CONSTRAINT ingredient_foods_aliases_pkey PRIMARY KEY (id, food_id);


--
-- Name: ingredient_foods ingredient_foods_name_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods
    ADD CONSTRAINT ingredient_foods_name_group_id_key UNIQUE (name, group_id);


--
-- Name: ingredient_foods ingredient_foods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods
    ADD CONSTRAINT ingredient_foods_pkey PRIMARY KEY (id);


--
-- Name: ingredient_foods_substitutions ingredient_foods_substitutions_food_ids_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods_substitutions
    ADD CONSTRAINT ingredient_foods_substitutions_food_ids_key UNIQUE (food_id, substitute_food_id);


--
-- Name: ingredient_foods_substitutions ingredient_foods_substitutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods_substitutions
    ADD CONSTRAINT ingredient_foods_substitutions_pkey PRIMARY KEY (id);


--
-- Name: ingredient_units_aliases ingredient_units_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_units_aliases
    ADD CONSTRAINT ingredient_units_aliases_pkey PRIMARY KEY (id, unit_id);


--
-- Name: ingredient_units ingredient_units_name_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_units
    ADD CONSTRAINT ingredient_units_name_group_id_key UNIQUE (name, group_id);


--
-- Name: ingredient_units ingredient_units_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_units
    ADD CONSTRAINT ingredient_units_pkey PRIMARY KEY (id);


--
-- Name: invite_tokens invite_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_tokens
    ADD CONSTRAINT invite_tokens_pkey PRIMARY KEY (id);


--
-- Name: long_live_tokens long_live_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.long_live_tokens
    ADD CONSTRAINT long_live_tokens_pkey PRIMARY KEY (id);


--
-- Name: multi_purpose_labels multi_purpose_labels_name_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multi_purpose_labels
    ADD CONSTRAINT multi_purpose_labels_name_group_id_key UNIQUE (name, group_id);


--
-- Name: multi_purpose_labels multi_purpose_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multi_purpose_labels
    ADD CONSTRAINT multi_purpose_labels_pkey PRIMARY KEY (id);


--
-- Name: notes notes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_pkey PRIMARY KEY (id);


--
-- Name: password_reset_tokens password_reset_tokens_token_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_token_key UNIQUE (token);


--
-- Name: plan_rules_to_tags plan_rule_id_tag_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_tags
    ADD CONSTRAINT plan_rule_id_tag_id_key UNIQUE (plan_rule_id, tag_id);


--
-- Name: recipe_actions recipe_actions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_actions
    ADD CONSTRAINT recipe_actions_pkey PRIMARY KEY (id);


--
-- Name: recipe_assets recipe_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_assets
    ADD CONSTRAINT recipe_assets_pkey PRIMARY KEY (id);


--
-- Name: recipe_comments recipe_comments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_comments
    ADD CONSTRAINT recipe_comments_pkey PRIMARY KEY (id);


--
-- Name: recipes_to_categories recipe_id_category_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_categories
    ADD CONSTRAINT recipe_id_category_id_key UNIQUE (recipe_id, category_id);


--
-- Name: recipes_to_tags recipe_id_tag_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_tags
    ADD CONSTRAINT recipe_id_tag_id_key UNIQUE (recipe_id, tag_id);


--
-- Name: recipes_to_tools recipe_id_tool_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_tools
    ADD CONSTRAINT recipe_id_tool_id_key UNIQUE (recipe_id, tool_id);


--
-- Name: recipe_ingredient_ref_link recipe_ingredient_ref_link_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredient_ref_link
    ADD CONSTRAINT recipe_ingredient_ref_link_pkey PRIMARY KEY (id);


--
-- Name: recipe_instructions recipe_instructions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_instructions
    ADD CONSTRAINT recipe_instructions_pkey PRIMARY KEY (id);


--
-- Name: recipe_note_ref_link recipe_note_ref_link_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_note_ref_link
    ADD CONSTRAINT recipe_note_ref_link_pkey PRIMARY KEY (id);


--
-- Name: recipe_nutrition recipe_nutrition_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_nutrition
    ADD CONSTRAINT recipe_nutrition_pkey PRIMARY KEY (id);


--
-- Name: recipe_settings recipe_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_settings
    ADD CONSTRAINT recipe_settings_pkey PRIMARY KEY (id);


--
-- Name: recipe_share_tokens recipe_share_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_share_tokens
    ADD CONSTRAINT recipe_share_tokens_pkey PRIMARY KEY (id);


--
-- Name: recipes recipe_slug_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes
    ADD CONSTRAINT recipe_slug_group_id_key UNIQUE (slug, group_id);


--
-- Name: recipe_timeline_events recipe_timeline_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_timeline_events
    ADD CONSTRAINT recipe_timeline_events_pkey PRIMARY KEY (id);


--
-- Name: recipes_ingredients recipes_ingredients_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients
    ADD CONSTRAINT recipes_ingredients_pkey PRIMARY KEY (id);


--
-- Name: recipes_ingredients_substitutions recipes_ingredients_substitutions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients_substitutions
    ADD CONSTRAINT recipes_ingredients_substitutions_pkey PRIMARY KEY (id);


--
-- Name: recipes recipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes
    ADD CONSTRAINT recipes_pkey PRIMARY KEY (id);


--
-- Name: report_entries report_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_entries
    ADD CONSTRAINT report_entries_pkey PRIMARY KEY (id);


--
-- Name: server_tasks server_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.server_tasks
    ADD CONSTRAINT server_tasks_pkey PRIMARY KEY (id);


--
-- Name: shopping_list_extras shopping_list_extras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_extras
    ADD CONSTRAINT shopping_list_extras_pkey PRIMARY KEY (id);


--
-- Name: shopping_lists_multi_purpose_labels shopping_list_id_label_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists_multi_purpose_labels
    ADD CONSTRAINT shopping_list_id_label_id_key UNIQUE (shopping_list_id, label_id);


--
-- Name: shopping_list_item_extras shopping_list_item_extras_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_item_extras
    ADD CONSTRAINT shopping_list_item_extras_pkey PRIMARY KEY (id);


--
-- Name: shopping_list_item_recipe_reference shopping_list_item_recipe_reference_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_item_recipe_reference
    ADD CONSTRAINT shopping_list_item_recipe_reference_pkey PRIMARY KEY (id, shopping_list_item_id);


--
-- Name: shopping_list_items shopping_list_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_items
    ADD CONSTRAINT shopping_list_items_pkey PRIMARY KEY (id);


--
-- Name: shopping_list_recipe_reference shopping_list_recipe_reference_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_recipe_reference
    ADD CONSTRAINT shopping_list_recipe_reference_pkey PRIMARY KEY (id, shopping_list_id);


--
-- Name: shopping_lists_multi_purpose_labels shopping_lists_multi_purpose_labels_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists_multi_purpose_labels
    ADD CONSTRAINT shopping_lists_multi_purpose_labels_pkey PRIMARY KEY (id, shopping_list_id, label_id);


--
-- Name: shopping_lists shopping_lists_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists
    ADD CONSTRAINT shopping_lists_pkey PRIMARY KEY (id);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- Name: tags tags_slug_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_slug_group_id_key UNIQUE (slug, group_id);


--
-- Name: tools tools_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_pkey PRIMARY KEY (id);


--
-- Name: tools tools_slug_group_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_slug_group_id_key UNIQUE (slug, group_id);


--
-- Name: users_to_recipes user_id_recipe_id_rating_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users_to_recipes
    ADD CONSTRAINT user_id_recipe_id_rating_key UNIQUE (user_id, recipe_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users_to_recipes users_to_recipes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users_to_recipes
    ADD CONSTRAINT users_to_recipes_pkey PRIMARY KEY (user_id, recipe_id, id);


--
-- Name: webhook_urls webhook_urls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_urls
    ADD CONSTRAINT webhook_urls_pkey PRIMARY KEY (id);


--
-- Name: ix_ai_provider_headers_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_headers_created_at ON public.ai_provider_headers USING btree (created_at);


--
-- Name: ix_ai_provider_headers_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_headers_provider_id ON public.ai_provider_headers USING btree (provider_id);


--
-- Name: ix_ai_provider_params_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_params_created_at ON public.ai_provider_params USING btree (created_at);


--
-- Name: ix_ai_provider_params_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_params_provider_id ON public.ai_provider_params USING btree (provider_id);


--
-- Name: ix_ai_provider_settings_audio_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_settings_audio_provider_id ON public.ai_provider_settings USING btree (audio_provider_id);


--
-- Name: ix_ai_provider_settings_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_settings_created_at ON public.ai_provider_settings USING btree (created_at);


--
-- Name: ix_ai_provider_settings_default_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_settings_default_provider_id ON public.ai_provider_settings USING btree (default_provider_id);


--
-- Name: ix_ai_provider_settings_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_settings_group_id ON public.ai_provider_settings USING btree (group_id);


--
-- Name: ix_ai_provider_settings_image_provider_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_provider_settings_image_provider_id ON public.ai_provider_settings USING btree (image_provider_id);


--
-- Name: ix_ai_providers_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_providers_created_at ON public.ai_providers USING btree (created_at);


--
-- Name: ix_ai_providers_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_providers_name ON public.ai_providers USING btree (name);


--
-- Name: ix_ai_providers_settings_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ai_providers_settings_id ON public.ai_providers USING btree (settings_id);


--
-- Name: ix_api_extras_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_api_extras_created_at ON public.api_extras USING btree (created_at);


--
-- Name: ix_api_extras_recipee_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_api_extras_recipee_id ON public.api_extras USING btree (recipee_id);


--
-- Name: ix_categories_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_created_at ON public.categories USING btree (created_at);


--
-- Name: ix_categories_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_group_id ON public.categories USING btree (group_id);


--
-- Name: ix_categories_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_name ON public.categories USING btree (name);


--
-- Name: ix_categories_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_categories_slug ON public.categories USING btree (slug);


--
-- Name: ix_cookbooks_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_created_at ON public.cookbooks USING btree (created_at);


--
-- Name: ix_cookbooks_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_group_id ON public.cookbooks USING btree (group_id);


--
-- Name: ix_cookbooks_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_household_id ON public.cookbooks USING btree (household_id);


--
-- Name: ix_cookbooks_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_slug ON public.cookbooks USING btree (slug);


--
-- Name: ix_cookbooks_to_categories_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_to_categories_category_id ON public.cookbooks_to_categories USING btree (category_id);


--
-- Name: ix_cookbooks_to_categories_cookbook_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_to_categories_cookbook_id ON public.cookbooks_to_categories USING btree (cookbook_id);


--
-- Name: ix_cookbooks_to_tags_cookbook_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_to_tags_cookbook_id ON public.cookbooks_to_tags USING btree (cookbook_id);


--
-- Name: ix_cookbooks_to_tags_tag_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_to_tags_tag_id ON public.cookbooks_to_tags USING btree (tag_id);


--
-- Name: ix_cookbooks_to_tools_cookbook_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_to_tools_cookbook_id ON public.cookbooks_to_tools USING btree (cookbook_id);


--
-- Name: ix_cookbooks_to_tools_tool_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_cookbooks_to_tools_tool_id ON public.cookbooks_to_tools USING btree (tool_id);


--
-- Name: ix_group_data_exports_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_data_exports_created_at ON public.group_data_exports USING btree (created_at);


--
-- Name: ix_group_data_exports_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_data_exports_group_id ON public.group_data_exports USING btree (group_id);


--
-- Name: ix_group_events_notifier_options_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_events_notifier_options_created_at ON public.group_events_notifier_options USING btree (created_at);


--
-- Name: ix_group_events_notifiers_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_events_notifiers_created_at ON public.group_events_notifiers USING btree (created_at);


--
-- Name: ix_group_events_notifiers_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_events_notifiers_group_id ON public.group_events_notifiers USING btree (group_id);


--
-- Name: ix_group_events_notifiers_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_events_notifiers_household_id ON public.group_events_notifiers USING btree (household_id);


--
-- Name: ix_group_meal_plan_rules_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plan_rules_created_at ON public.group_meal_plan_rules USING btree (created_at);


--
-- Name: ix_group_meal_plan_rules_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plan_rules_group_id ON public.group_meal_plan_rules USING btree (group_id);


--
-- Name: ix_group_meal_plan_rules_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plan_rules_household_id ON public.group_meal_plan_rules USING btree (household_id);


--
-- Name: ix_group_meal_plans_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_created_at ON public.group_meal_plans USING btree (created_at);


--
-- Name: ix_group_meal_plans_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_date ON public.group_meal_plans USING btree (date);


--
-- Name: ix_group_meal_plans_entry_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_entry_type ON public.group_meal_plans USING btree (entry_type);


--
-- Name: ix_group_meal_plans_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_group_id ON public.group_meal_plans USING btree (group_id);


--
-- Name: ix_group_meal_plans_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_recipe_id ON public.group_meal_plans USING btree (recipe_id);


--
-- Name: ix_group_meal_plans_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_title ON public.group_meal_plans USING btree (title);


--
-- Name: ix_group_meal_plans_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_meal_plans_user_id ON public.group_meal_plans USING btree (user_id);


--
-- Name: ix_group_preferences_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_preferences_created_at ON public.group_preferences USING btree (created_at);


--
-- Name: ix_group_preferences_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_preferences_group_id ON public.group_preferences USING btree (group_id);


--
-- Name: ix_group_reports_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_reports_category ON public.group_reports USING btree (category);


--
-- Name: ix_group_reports_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_reports_created_at ON public.group_reports USING btree (created_at);


--
-- Name: ix_group_reports_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_reports_group_id ON public.group_reports USING btree (group_id);


--
-- Name: ix_group_to_categories_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_to_categories_category_id ON public.group_to_categories USING btree (category_id);


--
-- Name: ix_group_to_categories_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_group_to_categories_group_id ON public.group_to_categories USING btree (group_id);


--
-- Name: ix_groups_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_groups_created_at ON public.groups USING btree (created_at);


--
-- Name: ix_groups_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_groups_name ON public.groups USING btree (name);


--
-- Name: ix_groups_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_groups_slug ON public.groups USING btree (slug);


--
-- Name: ix_household_preferences_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_household_preferences_created_at ON public.household_preferences USING btree (created_at);


--
-- Name: ix_household_preferences_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_household_preferences_household_id ON public.household_preferences USING btree (household_id);


--
-- Name: ix_households_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_created_at ON public.households USING btree (created_at);


--
-- Name: ix_households_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_group_id ON public.households USING btree (group_id);


--
-- Name: ix_households_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_name ON public.households USING btree (name);


--
-- Name: ix_households_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_slug ON public.households USING btree (slug);


--
-- Name: ix_households_to_ingredient_foods_food_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_ingredient_foods_food_id ON public.households_to_ingredient_foods USING btree (food_id);


--
-- Name: ix_households_to_ingredient_foods_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_ingredient_foods_household_id ON public.households_to_ingredient_foods USING btree (household_id);


--
-- Name: ix_households_to_recipes_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_recipes_created_at ON public.households_to_recipes USING btree (created_at);


--
-- Name: ix_households_to_recipes_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_recipes_household_id ON public.households_to_recipes USING btree (household_id);


--
-- Name: ix_households_to_recipes_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_recipes_recipe_id ON public.households_to_recipes USING btree (recipe_id);


--
-- Name: ix_households_to_tools_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_tools_household_id ON public.households_to_tools USING btree (household_id);


--
-- Name: ix_households_to_tools_tool_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_households_to_tools_tool_id ON public.households_to_tools USING btree (tool_id);


--
-- Name: ix_ingredient_food_extras_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_food_extras_created_at ON public.ingredient_food_extras USING btree (created_at);


--
-- Name: ix_ingredient_food_extras_ingredient_food_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_food_extras_ingredient_food_id ON public.ingredient_food_extras USING btree (ingredient_food_id);


--
-- Name: ix_ingredient_foods_aliases_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_aliases_created_at ON public.ingredient_foods_aliases USING btree (created_at);


--
-- Name: ix_ingredient_foods_aliases_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_aliases_name_normalized ON public.ingredient_foods_aliases USING btree (name_normalized);


--
-- Name: ix_ingredient_foods_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_created_at ON public.ingredient_foods USING btree (created_at);


--
-- Name: ix_ingredient_foods_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_group_id ON public.ingredient_foods USING btree (group_id);


--
-- Name: ix_ingredient_foods_label_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_label_id ON public.ingredient_foods USING btree (label_id);


--
-- Name: ix_ingredient_foods_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_name_normalized ON public.ingredient_foods USING btree (name_normalized);


--
-- Name: ix_ingredient_foods_plural_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_plural_name_normalized ON public.ingredient_foods USING btree (plural_name_normalized);


--
-- Name: ix_ingredient_foods_substitutions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_substitutions_created_at ON public.ingredient_foods_substitutions USING btree (created_at);


--
-- Name: ix_ingredient_foods_substitutions_food_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_substitutions_food_id ON public.ingredient_foods_substitutions USING btree (food_id);


--
-- Name: ix_ingredient_foods_substitutions_position; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_substitutions_position ON public.ingredient_foods_substitutions USING btree ("position");


--
-- Name: ix_ingredient_foods_substitutions_substitute_food_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_foods_substitutions_substitute_food_id ON public.ingredient_foods_substitutions USING btree (substitute_food_id);


--
-- Name: ix_ingredient_units_abbreviation_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_abbreviation_normalized ON public.ingredient_units USING btree (abbreviation_normalized);


--
-- Name: ix_ingredient_units_aliases_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_aliases_created_at ON public.ingredient_units_aliases USING btree (created_at);


--
-- Name: ix_ingredient_units_aliases_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_aliases_name_normalized ON public.ingredient_units_aliases USING btree (name_normalized);


--
-- Name: ix_ingredient_units_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_created_at ON public.ingredient_units USING btree (created_at);


--
-- Name: ix_ingredient_units_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_group_id ON public.ingredient_units USING btree (group_id);


--
-- Name: ix_ingredient_units_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_name_normalized ON public.ingredient_units USING btree (name_normalized);


--
-- Name: ix_ingredient_units_plural_abbreviation_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_plural_abbreviation_normalized ON public.ingredient_units USING btree (plural_abbreviation_normalized);


--
-- Name: ix_ingredient_units_plural_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_ingredient_units_plural_name_normalized ON public.ingredient_units USING btree (plural_name_normalized);


--
-- Name: ix_invite_tokens_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invite_tokens_created_at ON public.invite_tokens USING btree (created_at);


--
-- Name: ix_invite_tokens_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invite_tokens_group_id ON public.invite_tokens USING btree (group_id);


--
-- Name: ix_invite_tokens_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_invite_tokens_household_id ON public.invite_tokens USING btree (household_id);


--
-- Name: ix_invite_tokens_token; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_invite_tokens_token ON public.invite_tokens USING btree (token);


--
-- Name: ix_long_live_tokens_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_long_live_tokens_created_at ON public.long_live_tokens USING btree (created_at);


--
-- Name: ix_long_live_tokens_token; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_long_live_tokens_token ON public.long_live_tokens USING btree (token);


--
-- Name: ix_long_live_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_long_live_tokens_user_id ON public.long_live_tokens USING btree (user_id);


--
-- Name: ix_multi_purpose_labels_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multi_purpose_labels_created_at ON public.multi_purpose_labels USING btree (created_at);


--
-- Name: ix_multi_purpose_labels_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_multi_purpose_labels_group_id ON public.multi_purpose_labels USING btree (group_id);


--
-- Name: ix_notes_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notes_created_at ON public.notes USING btree (created_at);


--
-- Name: ix_notes_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notes_recipe_id ON public.notes USING btree (recipe_id);


--
-- Name: ix_notes_reference_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_notes_reference_id ON public.notes USING btree (reference_id);


--
-- Name: ix_password_reset_tokens_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_created_at ON public.password_reset_tokens USING btree (created_at);


--
-- Name: ix_password_reset_tokens_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_password_reset_tokens_user_id ON public.password_reset_tokens USING btree (user_id);


--
-- Name: ix_plan_rules_to_categories_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plan_rules_to_categories_category_id ON public.plan_rules_to_categories USING btree (category_id);


--
-- Name: ix_plan_rules_to_categories_group_plan_rule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plan_rules_to_categories_group_plan_rule_id ON public.plan_rules_to_categories USING btree (group_plan_rule_id);


--
-- Name: ix_plan_rules_to_households_group_plan_rule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plan_rules_to_households_group_plan_rule_id ON public.plan_rules_to_households USING btree (group_plan_rule_id);


--
-- Name: ix_plan_rules_to_households_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plan_rules_to_households_household_id ON public.plan_rules_to_households USING btree (household_id);


--
-- Name: ix_plan_rules_to_tags_plan_rule_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plan_rules_to_tags_plan_rule_id ON public.plan_rules_to_tags USING btree (plan_rule_id);


--
-- Name: ix_plan_rules_to_tags_tag_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_plan_rules_to_tags_tag_id ON public.plan_rules_to_tags USING btree (tag_id);


--
-- Name: ix_recipe_actions_action_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_actions_action_type ON public.recipe_actions USING btree (action_type);


--
-- Name: ix_recipe_actions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_actions_created_at ON public.recipe_actions USING btree (created_at);


--
-- Name: ix_recipe_actions_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_actions_group_id ON public.recipe_actions USING btree (group_id);


--
-- Name: ix_recipe_actions_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_actions_household_id ON public.recipe_actions USING btree (household_id);


--
-- Name: ix_recipe_actions_title; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_actions_title ON public.recipe_actions USING btree (title);


--
-- Name: ix_recipe_assets_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_assets_created_at ON public.recipe_assets USING btree (created_at);


--
-- Name: ix_recipe_assets_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_assets_recipe_id ON public.recipe_assets USING btree (recipe_id);


--
-- Name: ix_recipe_comments_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_comments_created_at ON public.recipe_comments USING btree (created_at);


--
-- Name: ix_recipe_comments_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_comments_recipe_id ON public.recipe_comments USING btree (recipe_id);


--
-- Name: ix_recipe_comments_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_comments_user_id ON public.recipe_comments USING btree (user_id);


--
-- Name: ix_recipe_ingredient_ref_link_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_ingredient_ref_link_created_at ON public.recipe_ingredient_ref_link USING btree (created_at);


--
-- Name: ix_recipe_ingredient_ref_link_instruction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_ingredient_ref_link_instruction_id ON public.recipe_ingredient_ref_link USING btree (instruction_id);


--
-- Name: ix_recipe_ingredient_ref_link_reference_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_ingredient_ref_link_reference_id ON public.recipe_ingredient_ref_link USING btree (reference_id);


--
-- Name: ix_recipe_instructions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_instructions_created_at ON public.recipe_instructions USING btree (created_at);


--
-- Name: ix_recipe_instructions_position; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_instructions_position ON public.recipe_instructions USING btree ("position");


--
-- Name: ix_recipe_instructions_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_instructions_recipe_id ON public.recipe_instructions USING btree (recipe_id);


--
-- Name: ix_recipe_note_ref_link_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_note_ref_link_created_at ON public.recipe_note_ref_link USING btree (created_at);


--
-- Name: ix_recipe_note_ref_link_instruction_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_note_ref_link_instruction_id ON public.recipe_note_ref_link USING btree (instruction_id);


--
-- Name: ix_recipe_note_ref_link_reference_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_note_ref_link_reference_id ON public.recipe_note_ref_link USING btree (reference_id);


--
-- Name: ix_recipe_nutrition_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_nutrition_created_at ON public.recipe_nutrition USING btree (created_at);


--
-- Name: ix_recipe_nutrition_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_nutrition_recipe_id ON public.recipe_nutrition USING btree (recipe_id);


--
-- Name: ix_recipe_settings_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_settings_created_at ON public.recipe_settings USING btree (created_at);


--
-- Name: ix_recipe_settings_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_settings_recipe_id ON public.recipe_settings USING btree (recipe_id);


--
-- Name: ix_recipe_share_tokens_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_share_tokens_created_at ON public.recipe_share_tokens USING btree (created_at);


--
-- Name: ix_recipe_share_tokens_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_share_tokens_group_id ON public.recipe_share_tokens USING btree (group_id);


--
-- Name: ix_recipe_share_tokens_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_share_tokens_recipe_id ON public.recipe_share_tokens USING btree (recipe_id);


--
-- Name: ix_recipe_timeline_events_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_timeline_events_created_at ON public.recipe_timeline_events USING btree (created_at);


--
-- Name: ix_recipe_timeline_events_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_timeline_events_recipe_id ON public.recipe_timeline_events USING btree (recipe_id);


--
-- Name: ix_recipe_timeline_events_timestamp; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_timeline_events_timestamp ON public.recipe_timeline_events USING btree ("timestamp");


--
-- Name: ix_recipe_timeline_events_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipe_timeline_events_user_id ON public.recipe_timeline_events USING btree (user_id);


--
-- Name: ix_recipes_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_created_at ON public.recipes USING btree (created_at);


--
-- Name: ix_recipes_description_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_description_normalized ON public.recipes USING btree (description_normalized);


--
-- Name: ix_recipes_description_normalized_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_description_normalized_gin ON public.recipes USING gin (description_normalized public.gin_trgm_ops);


--
-- Name: ix_recipes_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_group_id ON public.recipes USING btree (group_id);


--
-- Name: ix_recipes_ingredients_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_created_at ON public.recipes_ingredients USING btree (created_at);


--
-- Name: ix_recipes_ingredients_food_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_food_id ON public.recipes_ingredients USING btree (food_id);


--
-- Name: ix_recipes_ingredients_note_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_note_normalized ON public.recipes_ingredients USING btree (note_normalized);


--
-- Name: ix_recipes_ingredients_note_normalized_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_note_normalized_gin ON public.recipes_ingredients USING gin (note_normalized public.gin_trgm_ops);


--
-- Name: ix_recipes_ingredients_original_text_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_original_text_normalized ON public.recipes_ingredients USING btree (original_text_normalized);


--
-- Name: ix_recipes_ingredients_original_text_normalized_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_original_text_normalized_gin ON public.recipes_ingredients USING gin (original_text_normalized public.gin_trgm_ops);


--
-- Name: ix_recipes_ingredients_position; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_position ON public.recipes_ingredients USING btree ("position");


--
-- Name: ix_recipes_ingredients_referenced_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_referenced_recipe_id ON public.recipes_ingredients USING btree (referenced_recipe_id);


--
-- Name: ix_recipes_ingredients_substitutions_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_substitutions_created_at ON public.recipes_ingredients_substitutions USING btree (created_at);


--
-- Name: ix_recipes_ingredients_substitutions_ingredient_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_substitutions_ingredient_id ON public.recipes_ingredients_substitutions USING btree (ingredient_id);


--
-- Name: ix_recipes_ingredients_substitutions_position; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_substitutions_position ON public.recipes_ingredients_substitutions USING btree ("position");


--
-- Name: ix_recipes_ingredients_substitutions_substitute_food_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_substitutions_substitute_food_id ON public.recipes_ingredients_substitutions USING btree (substitute_food_id);


--
-- Name: ix_recipes_ingredients_unit_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_ingredients_unit_id ON public.recipes_ingredients USING btree (unit_id);


--
-- Name: ix_recipes_name_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_name_normalized ON public.recipes USING btree (name_normalized);


--
-- Name: ix_recipes_name_normalized_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_name_normalized_gin ON public.recipes USING gin (name_normalized public.gin_trgm_ops);


--
-- Name: ix_recipes_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_rating ON public.recipes USING btree (rating);


--
-- Name: ix_recipes_recipe_servings; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_recipe_servings ON public.recipes USING btree (recipe_servings);


--
-- Name: ix_recipes_recipe_yield_quantity; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_recipe_yield_quantity ON public.recipes USING btree (recipe_yield_quantity);


--
-- Name: ix_recipes_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_slug ON public.recipes USING btree (slug);


--
-- Name: ix_recipes_to_categories_category_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_to_categories_category_id ON public.recipes_to_categories USING btree (category_id);


--
-- Name: ix_recipes_to_categories_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_to_categories_recipe_id ON public.recipes_to_categories USING btree (recipe_id);


--
-- Name: ix_recipes_to_tags_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_to_tags_recipe_id ON public.recipes_to_tags USING btree (recipe_id);


--
-- Name: ix_recipes_to_tags_tag_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_to_tags_tag_id ON public.recipes_to_tags USING btree (tag_id);


--
-- Name: ix_recipes_to_tools_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_to_tools_recipe_id ON public.recipes_to_tools USING btree (recipe_id);


--
-- Name: ix_recipes_to_tools_tool_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_to_tools_tool_id ON public.recipes_to_tools USING btree (tool_id);


--
-- Name: ix_recipes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_recipes_user_id ON public.recipes USING btree (user_id);


--
-- Name: ix_report_entries_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_entries_created_at ON public.report_entries USING btree (created_at);


--
-- Name: ix_report_entries_report_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_report_entries_report_id ON public.report_entries USING btree (report_id);


--
-- Name: ix_server_tasks_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_server_tasks_created_at ON public.server_tasks USING btree (created_at);


--
-- Name: ix_server_tasks_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_server_tasks_group_id ON public.server_tasks USING btree (group_id);


--
-- Name: ix_shopping_list_extras_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_extras_created_at ON public.shopping_list_extras USING btree (created_at);


--
-- Name: ix_shopping_list_extras_shopping_list_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_extras_shopping_list_id ON public.shopping_list_extras USING btree (shopping_list_id);


--
-- Name: ix_shopping_list_item_extras_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_item_extras_created_at ON public.shopping_list_item_extras USING btree (created_at);


--
-- Name: ix_shopping_list_item_extras_shopping_list_item_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_item_extras_shopping_list_item_id ON public.shopping_list_item_extras USING btree (shopping_list_item_id);


--
-- Name: ix_shopping_list_item_recipe_reference_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_item_recipe_reference_created_at ON public.shopping_list_item_recipe_reference USING btree (created_at);


--
-- Name: ix_shopping_list_item_recipe_reference_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_item_recipe_reference_recipe_id ON public.shopping_list_item_recipe_reference USING btree (recipe_id);


--
-- Name: ix_shopping_list_items_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_items_created_at ON public.shopping_list_items USING btree (created_at);


--
-- Name: ix_shopping_list_items_position; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_items_position ON public.shopping_list_items USING btree ("position");


--
-- Name: ix_shopping_list_items_shopping_list_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_items_shopping_list_id ON public.shopping_list_items USING btree (shopping_list_id);


--
-- Name: ix_shopping_list_recipe_reference_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_recipe_reference_created_at ON public.shopping_list_recipe_reference USING btree (created_at);


--
-- Name: ix_shopping_list_recipe_reference_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_list_recipe_reference_recipe_id ON public.shopping_list_recipe_reference USING btree (recipe_id);


--
-- Name: ix_shopping_lists_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_lists_created_at ON public.shopping_lists USING btree (created_at);


--
-- Name: ix_shopping_lists_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_lists_group_id ON public.shopping_lists USING btree (group_id);


--
-- Name: ix_shopping_lists_multi_purpose_labels_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_lists_multi_purpose_labels_created_at ON public.shopping_lists_multi_purpose_labels USING btree (created_at);


--
-- Name: ix_shopping_lists_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_shopping_lists_user_id ON public.shopping_lists USING btree (user_id);


--
-- Name: ix_tags_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tags_created_at ON public.tags USING btree (created_at);


--
-- Name: ix_tags_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tags_group_id ON public.tags USING btree (group_id);


--
-- Name: ix_tags_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tags_name ON public.tags USING btree (name);


--
-- Name: ix_tags_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tags_slug ON public.tags USING btree (slug);


--
-- Name: ix_tools_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tools_created_at ON public.tools USING btree (created_at);


--
-- Name: ix_tools_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tools_group_id ON public.tools USING btree (group_id);


--
-- Name: ix_tools_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tools_name ON public.tools USING btree (name);


--
-- Name: ix_tools_slug; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_tools_slug ON public.tools USING btree (slug);


--
-- Name: ix_users_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_created_at ON public.users USING btree (created_at);


--
-- Name: ix_users_email; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_email ON public.users USING btree (email);


--
-- Name: ix_users_full_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_full_name ON public.users USING btree (full_name);


--
-- Name: ix_users_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_group_id ON public.users USING btree (group_id);


--
-- Name: ix_users_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_household_id ON public.users USING btree (household_id);


--
-- Name: ix_users_to_recipes_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_to_recipes_created_at ON public.users_to_recipes USING btree (created_at);


--
-- Name: ix_users_to_recipes_is_favorite; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_to_recipes_is_favorite ON public.users_to_recipes USING btree (is_favorite);


--
-- Name: ix_users_to_recipes_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_to_recipes_rating ON public.users_to_recipes USING btree (rating);


--
-- Name: ix_users_to_recipes_recipe_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_to_recipes_recipe_id ON public.users_to_recipes USING btree (recipe_id);


--
-- Name: ix_users_to_recipes_user_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_users_to_recipes_user_id ON public.users_to_recipes USING btree (user_id);


--
-- Name: ix_users_username; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_users_username ON public.users USING btree (username);


--
-- Name: ix_webhook_urls_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_urls_created_at ON public.webhook_urls USING btree (created_at);


--
-- Name: ix_webhook_urls_group_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_urls_group_id ON public.webhook_urls USING btree (group_id);


--
-- Name: ix_webhook_urls_household_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_webhook_urls_household_id ON public.webhook_urls USING btree (household_id);


--
-- Name: ai_provider_headers ai_provider_headers_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_headers
    ADD CONSTRAINT ai_provider_headers_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.ai_providers(id);


--
-- Name: ai_provider_params ai_provider_params_provider_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_params
    ADD CONSTRAINT ai_provider_params_provider_id_fkey FOREIGN KEY (provider_id) REFERENCES public.ai_providers(id);


--
-- Name: ai_provider_settings ai_provider_settings_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_provider_settings
    ADD CONSTRAINT ai_provider_settings_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: ai_providers ai_providers_settings_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ai_providers
    ADD CONSTRAINT ai_providers_settings_id_fkey FOREIGN KEY (settings_id) REFERENCES public.ai_provider_settings(id);


--
-- Name: api_extras api_extras_recipee_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_extras
    ADD CONSTRAINT api_extras_recipee_id_fkey FOREIGN KEY (recipee_id) REFERENCES public.recipes(id);


--
-- Name: categories categories_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.categories
    ADD CONSTRAINT categories_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: cookbooks cookbooks_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks
    ADD CONSTRAINT cookbooks_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: cookbooks_to_categories cookbooks_to_categories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_categories
    ADD CONSTRAINT cookbooks_to_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: cookbooks_to_categories cookbooks_to_categories_cookbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_categories
    ADD CONSTRAINT cookbooks_to_categories_cookbook_id_fkey FOREIGN KEY (cookbook_id) REFERENCES public.cookbooks(id);


--
-- Name: cookbooks_to_tags cookbooks_to_tags_cookbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_tags
    ADD CONSTRAINT cookbooks_to_tags_cookbook_id_fkey FOREIGN KEY (cookbook_id) REFERENCES public.cookbooks(id);


--
-- Name: cookbooks_to_tags cookbooks_to_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_tags
    ADD CONSTRAINT cookbooks_to_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id);


--
-- Name: cookbooks_to_tools cookbooks_to_tools_cookbook_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_tools
    ADD CONSTRAINT cookbooks_to_tools_cookbook_id_fkey FOREIGN KEY (cookbook_id) REFERENCES public.cookbooks(id);


--
-- Name: cookbooks_to_tools cookbooks_to_tools_tool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks_to_tools
    ADD CONSTRAINT cookbooks_to_tools_tool_id_fkey FOREIGN KEY (tool_id) REFERENCES public.tools(id);


--
-- Name: cookbooks fk_cookbooks_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.cookbooks
    ADD CONSTRAINT fk_cookbooks_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: group_events_notifiers fk_group_events_notifiers_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_events_notifiers
    ADD CONSTRAINT fk_group_events_notifiers_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: group_meal_plan_rules fk_group_meal_plan_rules_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plan_rules
    ADD CONSTRAINT fk_group_meal_plan_rules_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: invite_tokens fk_invite_tokens_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_tokens
    ADD CONSTRAINT fk_invite_tokens_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: recipe_actions fk_recipe_actions_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_actions
    ADD CONSTRAINT fk_recipe_actions_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: recipes_ingredients fk_recipe_subrecipe; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients
    ADD CONSTRAINT fk_recipe_subrecipe FOREIGN KEY (referenced_recipe_id) REFERENCES public.recipes(id);


--
-- Name: group_meal_plans fk_user_mealplans; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plans
    ADD CONSTRAINT fk_user_mealplans FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: shopping_lists fk_user_shopping_lists; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists
    ADD CONSTRAINT fk_user_shopping_lists FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: users fk_users_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT fk_users_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: webhook_urls fk_webhook_urls_household_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_urls
    ADD CONSTRAINT fk_webhook_urls_household_id FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: group_data_exports group_data_exports_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_data_exports
    ADD CONSTRAINT group_data_exports_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_events_notifier_options group_events_notifier_options_event_notifier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_events_notifier_options
    ADD CONSTRAINT group_events_notifier_options_event_notifier_id_fkey FOREIGN KEY (event_notifier_id) REFERENCES public.group_events_notifiers(id);


--
-- Name: group_events_notifiers group_events_notifiers_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_events_notifiers
    ADD CONSTRAINT group_events_notifiers_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_meal_plan_rules group_meal_plan_rules_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plan_rules
    ADD CONSTRAINT group_meal_plan_rules_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_meal_plans group_meal_plans_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plans
    ADD CONSTRAINT group_meal_plans_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_meal_plans group_meal_plans_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_meal_plans
    ADD CONSTRAINT group_meal_plans_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: group_preferences group_preferences_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_preferences
    ADD CONSTRAINT group_preferences_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_reports group_reports_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_reports
    ADD CONSTRAINT group_reports_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: group_to_categories group_to_categories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_to_categories
    ADD CONSTRAINT group_to_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: group_to_categories group_to_categories_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.group_to_categories
    ADD CONSTRAINT group_to_categories_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: household_preferences household_preferences_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.household_preferences
    ADD CONSTRAINT household_preferences_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: households households_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households
    ADD CONSTRAINT households_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: households_to_ingredient_foods households_to_ingredient_foods_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_ingredient_foods
    ADD CONSTRAINT households_to_ingredient_foods_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: households_to_ingredient_foods households_to_ingredient_foods_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_ingredient_foods
    ADD CONSTRAINT households_to_ingredient_foods_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: households_to_recipes households_to_recipes_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_recipes
    ADD CONSTRAINT households_to_recipes_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: households_to_recipes households_to_recipes_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_recipes
    ADD CONSTRAINT households_to_recipes_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: households_to_tools households_to_tools_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_tools
    ADD CONSTRAINT households_to_tools_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: households_to_tools households_to_tools_tool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.households_to_tools
    ADD CONSTRAINT households_to_tools_tool_id_fkey FOREIGN KEY (tool_id) REFERENCES public.tools(id);


--
-- Name: ingredient_food_extras ingredient_food_extras_ingredient_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_food_extras
    ADD CONSTRAINT ingredient_food_extras_ingredient_food_id_fkey FOREIGN KEY (ingredient_food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: ingredient_foods_aliases ingredient_foods_aliases_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods_aliases
    ADD CONSTRAINT ingredient_foods_aliases_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: ingredient_foods ingredient_foods_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods
    ADD CONSTRAINT ingredient_foods_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: ingredient_foods ingredient_foods_label_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods
    ADD CONSTRAINT ingredient_foods_label_id_fkey FOREIGN KEY (label_id) REFERENCES public.multi_purpose_labels(id);


--
-- Name: ingredient_foods_substitutions ingredient_foods_substitutions_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods_substitutions
    ADD CONSTRAINT ingredient_foods_substitutions_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: ingredient_foods_substitutions ingredient_foods_substitutions_substitute_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_foods_substitutions
    ADD CONSTRAINT ingredient_foods_substitutions_substitute_food_id_fkey FOREIGN KEY (substitute_food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: ingredient_units_aliases ingredient_units_aliases_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_units_aliases
    ADD CONSTRAINT ingredient_units_aliases_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES public.ingredient_units(id);


--
-- Name: ingredient_units ingredient_units_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.ingredient_units
    ADD CONSTRAINT ingredient_units_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: invite_tokens invite_tokens_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.invite_tokens
    ADD CONSTRAINT invite_tokens_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: long_live_tokens long_live_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.long_live_tokens
    ADD CONSTRAINT long_live_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: multi_purpose_labels multi_purpose_labels_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.multi_purpose_labels
    ADD CONSTRAINT multi_purpose_labels_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: notes notes_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notes
    ADD CONSTRAINT notes_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: password_reset_tokens password_reset_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.password_reset_tokens
    ADD CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: plan_rules_to_categories plan_rules_to_categories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_categories
    ADD CONSTRAINT plan_rules_to_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: plan_rules_to_categories plan_rules_to_categories_group_plan_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_categories
    ADD CONSTRAINT plan_rules_to_categories_group_plan_rule_id_fkey FOREIGN KEY (group_plan_rule_id) REFERENCES public.group_meal_plan_rules(id);


--
-- Name: plan_rules_to_households plan_rules_to_households_group_plan_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_households
    ADD CONSTRAINT plan_rules_to_households_group_plan_rule_id_fkey FOREIGN KEY (group_plan_rule_id) REFERENCES public.group_meal_plan_rules(id);


--
-- Name: plan_rules_to_households plan_rules_to_households_household_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_households
    ADD CONSTRAINT plan_rules_to_households_household_id_fkey FOREIGN KEY (household_id) REFERENCES public.households(id);


--
-- Name: plan_rules_to_tags plan_rules_to_tags_plan_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_tags
    ADD CONSTRAINT plan_rules_to_tags_plan_rule_id_fkey FOREIGN KEY (plan_rule_id) REFERENCES public.group_meal_plan_rules(id);


--
-- Name: plan_rules_to_tags plan_rules_to_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.plan_rules_to_tags
    ADD CONSTRAINT plan_rules_to_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id);


--
-- Name: recipe_actions recipe_actions_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_actions
    ADD CONSTRAINT recipe_actions_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: recipe_assets recipe_assets_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_assets
    ADD CONSTRAINT recipe_assets_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_comments recipe_comments_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_comments
    ADD CONSTRAINT recipe_comments_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_comments recipe_comments_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_comments
    ADD CONSTRAINT recipe_comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: recipe_ingredient_ref_link recipe_ingredient_ref_link_instruction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_ingredient_ref_link
    ADD CONSTRAINT recipe_ingredient_ref_link_instruction_id_fkey FOREIGN KEY (instruction_id) REFERENCES public.recipe_instructions(id);


--
-- Name: recipe_instructions recipe_instructions_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_instructions
    ADD CONSTRAINT recipe_instructions_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_note_ref_link recipe_note_ref_link_instruction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_note_ref_link
    ADD CONSTRAINT recipe_note_ref_link_instruction_id_fkey FOREIGN KEY (instruction_id) REFERENCES public.recipe_instructions(id);


--
-- Name: recipe_nutrition recipe_nutrition_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_nutrition
    ADD CONSTRAINT recipe_nutrition_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_settings recipe_settings_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_settings
    ADD CONSTRAINT recipe_settings_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_share_tokens recipe_share_tokens_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_share_tokens
    ADD CONSTRAINT recipe_share_tokens_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: recipe_share_tokens recipe_share_tokens_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_share_tokens
    ADD CONSTRAINT recipe_share_tokens_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_timeline_events recipe_timeline_events_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_timeline_events
    ADD CONSTRAINT recipe_timeline_events_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipe_timeline_events recipe_timeline_events_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipe_timeline_events
    ADD CONSTRAINT recipe_timeline_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: recipes recipes_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes
    ADD CONSTRAINT recipes_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: recipes_ingredients recipes_ingredients_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients
    ADD CONSTRAINT recipes_ingredients_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: recipes_ingredients recipes_ingredients_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients
    ADD CONSTRAINT recipes_ingredients_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipes_ingredients_substitutions recipes_ingredients_substitutions_ingredient_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients_substitutions
    ADD CONSTRAINT recipes_ingredients_substitutions_ingredient_id_fkey FOREIGN KEY (ingredient_id) REFERENCES public.recipes_ingredients(id);


--
-- Name: recipes_ingredients_substitutions recipes_ingredients_substitutions_substitute_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients_substitutions
    ADD CONSTRAINT recipes_ingredients_substitutions_substitute_food_id_fkey FOREIGN KEY (substitute_food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: recipes_ingredients recipes_ingredients_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_ingredients
    ADD CONSTRAINT recipes_ingredients_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES public.ingredient_units(id);


--
-- Name: recipes_to_categories recipes_to_categories_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_categories
    ADD CONSTRAINT recipes_to_categories_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(id);


--
-- Name: recipes_to_categories recipes_to_categories_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_categories
    ADD CONSTRAINT recipes_to_categories_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipes_to_tags recipes_to_tags_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_tags
    ADD CONSTRAINT recipes_to_tags_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipes_to_tags recipes_to_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_tags
    ADD CONSTRAINT recipes_to_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id);


--
-- Name: recipes_to_tools recipes_to_tools_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_tools
    ADD CONSTRAINT recipes_to_tools_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: recipes_to_tools recipes_to_tools_tool_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.recipes_to_tools
    ADD CONSTRAINT recipes_to_tools_tool_id_fkey FOREIGN KEY (tool_id) REFERENCES public.tools(id);


--
-- Name: report_entries report_entries_report_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.report_entries
    ADD CONSTRAINT report_entries_report_id_fkey FOREIGN KEY (report_id) REFERENCES public.group_reports(id);


--
-- Name: server_tasks server_tasks_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.server_tasks
    ADD CONSTRAINT server_tasks_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: shopping_list_extras shopping_list_extras_shopping_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_extras
    ADD CONSTRAINT shopping_list_extras_shopping_list_id_fkey FOREIGN KEY (shopping_list_id) REFERENCES public.shopping_lists(id);


--
-- Name: shopping_list_item_extras shopping_list_item_extras_shopping_list_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_item_extras
    ADD CONSTRAINT shopping_list_item_extras_shopping_list_item_id_fkey FOREIGN KEY (shopping_list_item_id) REFERENCES public.shopping_list_items(id);


--
-- Name: shopping_list_item_recipe_reference shopping_list_item_recipe_reference_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_item_recipe_reference
    ADD CONSTRAINT shopping_list_item_recipe_reference_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: shopping_list_item_recipe_reference shopping_list_item_recipe_reference_shopping_list_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_item_recipe_reference
    ADD CONSTRAINT shopping_list_item_recipe_reference_shopping_list_item_id_fkey FOREIGN KEY (shopping_list_item_id) REFERENCES public.shopping_list_items(id);


--
-- Name: shopping_list_items shopping_list_items_food_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_items
    ADD CONSTRAINT shopping_list_items_food_id_fkey FOREIGN KEY (food_id) REFERENCES public.ingredient_foods(id);


--
-- Name: shopping_list_items shopping_list_items_label_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_items
    ADD CONSTRAINT shopping_list_items_label_id_fkey FOREIGN KEY (label_id) REFERENCES public.multi_purpose_labels(id);


--
-- Name: shopping_list_items shopping_list_items_shopping_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_items
    ADD CONSTRAINT shopping_list_items_shopping_list_id_fkey FOREIGN KEY (shopping_list_id) REFERENCES public.shopping_lists(id);


--
-- Name: shopping_list_items shopping_list_items_unit_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_items
    ADD CONSTRAINT shopping_list_items_unit_id_fkey FOREIGN KEY (unit_id) REFERENCES public.ingredient_units(id);


--
-- Name: shopping_list_recipe_reference shopping_list_recipe_reference_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_recipe_reference
    ADD CONSTRAINT shopping_list_recipe_reference_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: shopping_list_recipe_reference shopping_list_recipe_reference_shopping_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_list_recipe_reference
    ADD CONSTRAINT shopping_list_recipe_reference_shopping_list_id_fkey FOREIGN KEY (shopping_list_id) REFERENCES public.shopping_lists(id);


--
-- Name: shopping_lists shopping_lists_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists
    ADD CONSTRAINT shopping_lists_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: shopping_lists_multi_purpose_labels shopping_lists_multi_purpose_labels_label_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists_multi_purpose_labels
    ADD CONSTRAINT shopping_lists_multi_purpose_labels_label_id_fkey FOREIGN KEY (label_id) REFERENCES public.multi_purpose_labels(id);


--
-- Name: shopping_lists_multi_purpose_labels shopping_lists_multi_purpose_labels_shopping_list_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.shopping_lists_multi_purpose_labels
    ADD CONSTRAINT shopping_lists_multi_purpose_labels_shopping_list_id_fkey FOREIGN KEY (shopping_list_id) REFERENCES public.shopping_lists(id);


--
-- Name: tags tags_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: tools tools_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tools
    ADD CONSTRAINT tools_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: users users_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- Name: users users_owned_recipes_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_owned_recipes_id_fkey FOREIGN KEY (owned_recipes_id) REFERENCES public.recipes(id);


--
-- Name: users_to_recipes users_to_recipes_recipe_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users_to_recipes
    ADD CONSTRAINT users_to_recipes_recipe_id_fkey FOREIGN KEY (recipe_id) REFERENCES public.recipes(id);


--
-- Name: users_to_recipes users_to_recipes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.users_to_recipes
    ADD CONSTRAINT users_to_recipes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: webhook_urls webhook_urls_group_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.webhook_urls
    ADD CONSTRAINT webhook_urls_group_id_fkey FOREIGN KEY (group_id) REFERENCES public.groups(id);


--
-- PostgreSQL database dump complete
--


