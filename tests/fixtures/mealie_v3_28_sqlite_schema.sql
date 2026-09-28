-- Mealie v3.28.0 SQLite schema (.schema of a fresh install), for CookDex's
-- direct-database integration tests. Structure only; no data.
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
CREATE TABLE groups (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, slug VARCHAR, 
	PRIMARY KEY (id)
);
CREATE UNIQUE INDEX ix_groups_name ON groups (name);
CREATE TABLE categories (
	created_at DATETIME, 
	update_at DATETIME, 
	group_id CHAR(32) NOT NULL, 
	id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	slug VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	CONSTRAINT category_slug_group_id_key UNIQUE (slug, group_id)
);
CREATE INDEX ix_categories_group_id ON categories (group_id);
CREATE INDEX ix_categories_name ON categories (name);
CREATE INDEX ix_categories_slug ON categories (slug);
CREATE TABLE group_data_exports (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32), 
	name VARCHAR NOT NULL, 
	filename VARCHAR NOT NULL, 
	path VARCHAR NOT NULL, 
	size VARCHAR NOT NULL, 
	expires VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_group_data_exports_group_id ON group_data_exports (group_id);
CREATE TABLE group_reports (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	category VARCHAR NOT NULL, 
	timestamp DATETIME NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_group_reports_category ON group_reports (category);
CREATE INDEX ix_group_reports_group_id ON group_reports (group_id);
CREATE TABLE server_tasks (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	name VARCHAR NOT NULL, 
	completed_date DATETIME, 
	status VARCHAR NOT NULL, 
	log VARCHAR, 
	group_id CHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_server_tasks_group_id ON server_tasks (group_id);
CREATE TABLE tags (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	slug VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	CONSTRAINT tags_slug_group_id_key UNIQUE (slug, group_id)
);
CREATE INDEX ix_tags_group_id ON tags (group_id);
CREATE INDEX ix_tags_name ON tags (name);
CREATE INDEX ix_tags_slug ON tags (slug);
CREATE TABLE tools (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	slug VARCHAR NOT NULL, 
	on_hand BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	CONSTRAINT tools_slug_group_id_key UNIQUE (slug, group_id)
);
CREATE TABLE api_extras (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	recipee_id CHAR(32), 
	key_name VARCHAR, 
	value VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipee_id) REFERENCES recipes (id)
);
CREATE TABLE notes (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	recipe_id CHAR(32), 
	title VARCHAR, 
	text VARCHAR, reference_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE TABLE recipe_assets (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	recipe_id CHAR(32), 
	name VARCHAR, 
	icon VARCHAR, 
	file_name VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE TABLE recipe_instructions (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	recipe_id CHAR(32), 
	position INTEGER, 
	type VARCHAR, 
	title VARCHAR, 
	text VARCHAR, summary VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE TABLE recipe_nutrition (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	recipe_id CHAR(32), 
	calories VARCHAR, 
	fat_content VARCHAR, 
	fiber_content VARCHAR, 
	protein_content VARCHAR, 
	carbohydrate_content VARCHAR, 
	sodium_content VARCHAR, 
	sugar_content VARCHAR, cholesterol_content VARCHAR, saturated_fat_content VARCHAR, trans_fat_content VARCHAR, unsaturated_fat_content VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE TABLE recipe_settings (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	recipe_id CHAR(32), 
	public BOOLEAN, 
	show_nutrition BOOLEAN, 
	show_assets BOOLEAN, 
	landscape_view BOOLEAN, 
	disable_amount BOOLEAN, 
	disable_comments BOOLEAN, 
	locked BOOLEAN, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE TABLE recipe_share_tokens (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	recipe_id CHAR(32) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE INDEX ix_recipe_share_tokens_group_id ON recipe_share_tokens (group_id);
CREATE TABLE report_entries (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	success BOOLEAN, 
	message VARCHAR, 
	exception VARCHAR, 
	timestamp DATETIME NOT NULL, 
	report_id CHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(report_id) REFERENCES group_reports (id)
);
CREATE TABLE shopping_list_recipe_reference (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	shopping_list_id CHAR(32) NOT NULL, 
	recipe_id CHAR(32), 
	recipe_quantity FLOAT NOT NULL, 
	PRIMARY KEY (id, shopping_list_id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(shopping_list_id) REFERENCES shopping_lists (id)
);
CREATE INDEX ix_shopping_list_recipe_reference_recipe_id ON shopping_list_recipe_reference (recipe_id);
CREATE TABLE long_live_tokens (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	name VARCHAR NOT NULL, 
	token VARCHAR NOT NULL, 
	user_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE password_reset_tokens (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	user_id CHAR(32) NOT NULL, 
	token VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	UNIQUE (token)
);
CREATE TABLE recipe_comments (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	text VARCHAR, 
	recipe_id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE recipe_ingredient_ref_link (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	instruction_id CHAR(32), 
	reference_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(instruction_id) REFERENCES recipe_instructions (id)
);
CREATE TABLE shopping_list_items (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	shopping_list_id CHAR(32), 
	is_ingredient BOOLEAN, 
	position INTEGER NOT NULL, 
	checked BOOLEAN, 
	quantity FLOAT, 
	note VARCHAR, 
	is_food BOOLEAN, 
	unit_id CHAR(32), 
	food_id CHAR(32), 
	label_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(food_id) REFERENCES ingredient_foods (id), 
	FOREIGN KEY(label_id) REFERENCES multi_purpose_labels (id), 
	FOREIGN KEY(shopping_list_id) REFERENCES shopping_lists (id), 
	FOREIGN KEY(unit_id) REFERENCES ingredient_units (id)
);
CREATE TABLE shopping_list_extras (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	key_name VARCHAR, 
	value VARCHAR, 
	shopping_list_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(shopping_list_id) REFERENCES shopping_lists (id)
);
CREATE TABLE ingredient_food_extras (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	key_name VARCHAR, 
	value VARCHAR, 
	ingredient_food_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(ingredient_food_id) REFERENCES ingredient_foods (id)
);
CREATE TABLE shopping_list_item_extras (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	key_name VARCHAR, 
	value VARCHAR, 
	shopping_list_item_id CHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(shopping_list_item_id) REFERENCES shopping_list_items (id)
);
CREATE TABLE recipe_timeline_events (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	recipe_id CHAR(32) NOT NULL, 
	user_id CHAR(32) NOT NULL, 
	subject VARCHAR NOT NULL, 
	message VARCHAR, 
	event_type VARCHAR, 
	image VARCHAR, 
	timestamp DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE TABLE "group_meal_plans" (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	date DATE NOT NULL, 
	entry_type VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	text VARCHAR NOT NULL, 
	group_id CHAR(32), 
	recipe_id CHAR(32), 
	user_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_user_mealplans FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE INDEX ix_group_meal_plans_title ON group_meal_plans (title);
CREATE INDEX ix_group_meal_plans_entry_type ON group_meal_plans (entry_type);
CREATE INDEX ix_group_meal_plans_recipe_id ON group_meal_plans (recipe_id);
CREATE INDEX ix_group_meal_plans_group_id ON group_meal_plans (group_id);
CREATE INDEX ix_group_meal_plans_date ON group_meal_plans (date);
CREATE INDEX ix_group_meal_plans_user_id ON group_meal_plans (user_id);
CREATE TABLE "shopping_list_item_recipe_reference" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	shopping_list_item_id CHAR(32) NOT NULL, 
	recipe_id CHAR(32), 
	recipe_quantity FLOAT NOT NULL, 
	recipe_scale FLOAT NOT NULL, recipe_note VARCHAR, 
	PRIMARY KEY (id, shopping_list_item_id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(shopping_list_item_id) REFERENCES shopping_list_items (id)
);
CREATE INDEX ix_shopping_list_item_recipe_reference_recipe_id ON shopping_list_item_recipe_reference (recipe_id);
CREATE INDEX ix_api_extras_created_at ON api_extras (created_at);
CREATE INDEX ix_api_extras_recipee_id ON api_extras (recipee_id);
CREATE INDEX ix_categories_created_at ON categories (created_at);
CREATE INDEX ix_group_data_exports_created_at ON group_data_exports (created_at);
CREATE INDEX ix_group_meal_plans_created_at ON group_meal_plans (created_at);
CREATE INDEX ix_group_reports_created_at ON group_reports (created_at);
CREATE INDEX ix_groups_created_at ON groups (created_at);
CREATE INDEX ix_ingredient_food_extras_created_at ON ingredient_food_extras (created_at);
CREATE INDEX ix_ingredient_food_extras_ingredient_food_id ON ingredient_food_extras (ingredient_food_id);
CREATE INDEX ix_long_live_tokens_created_at ON long_live_tokens (created_at);
CREATE INDEX ix_long_live_tokens_token ON long_live_tokens (token);
CREATE INDEX ix_long_live_tokens_user_id ON long_live_tokens (user_id);
CREATE INDEX ix_notes_created_at ON notes (created_at);
CREATE INDEX ix_notes_recipe_id ON notes (recipe_id);
CREATE INDEX ix_password_reset_tokens_created_at ON password_reset_tokens (created_at);
CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);
CREATE INDEX ix_recipe_assets_created_at ON recipe_assets (created_at);
CREATE INDEX ix_recipe_assets_recipe_id ON recipe_assets (recipe_id);
CREATE INDEX ix_recipe_comments_created_at ON recipe_comments (created_at);
CREATE INDEX ix_recipe_comments_recipe_id ON recipe_comments (recipe_id);
CREATE INDEX ix_recipe_comments_user_id ON recipe_comments (user_id);
CREATE INDEX ix_recipe_ingredient_ref_link_created_at ON recipe_ingredient_ref_link (created_at);
CREATE INDEX ix_recipe_ingredient_ref_link_instruction_id ON recipe_ingredient_ref_link (instruction_id);
CREATE INDEX ix_recipe_ingredient_ref_link_reference_id ON recipe_ingredient_ref_link (reference_id);
CREATE INDEX ix_recipe_instructions_created_at ON recipe_instructions (created_at);
CREATE INDEX ix_recipe_instructions_position ON recipe_instructions (position);
CREATE INDEX ix_recipe_instructions_recipe_id ON recipe_instructions (recipe_id);
CREATE INDEX ix_recipe_nutrition_created_at ON recipe_nutrition (created_at);
CREATE INDEX ix_recipe_nutrition_recipe_id ON recipe_nutrition (recipe_id);
CREATE INDEX ix_recipe_settings_created_at ON recipe_settings (created_at);
CREATE INDEX ix_recipe_settings_recipe_id ON recipe_settings (recipe_id);
CREATE INDEX ix_recipe_share_tokens_created_at ON recipe_share_tokens (created_at);
CREATE INDEX ix_recipe_share_tokens_recipe_id ON recipe_share_tokens (recipe_id);
CREATE INDEX ix_recipe_timeline_events_created_at ON recipe_timeline_events (created_at);
CREATE INDEX ix_recipe_timeline_events_recipe_id ON recipe_timeline_events (recipe_id);
CREATE INDEX ix_recipe_timeline_events_timestamp ON recipe_timeline_events (timestamp);
CREATE INDEX ix_recipe_timeline_events_user_id ON recipe_timeline_events (user_id);
CREATE INDEX ix_report_entries_created_at ON report_entries (created_at);
CREATE INDEX ix_report_entries_report_id ON report_entries (report_id);
CREATE INDEX ix_server_tasks_created_at ON server_tasks (created_at);
CREATE INDEX ix_shopping_list_extras_created_at ON shopping_list_extras (created_at);
CREATE INDEX ix_shopping_list_extras_shopping_list_id ON shopping_list_extras (shopping_list_id);
CREATE INDEX ix_shopping_list_item_extras_created_at ON shopping_list_item_extras (created_at);
CREATE INDEX ix_shopping_list_item_extras_shopping_list_item_id ON shopping_list_item_extras (shopping_list_item_id);
CREATE INDEX ix_shopping_list_item_recipe_reference_created_at ON shopping_list_item_recipe_reference (created_at);
CREATE INDEX ix_shopping_list_items_created_at ON shopping_list_items (created_at);
CREATE INDEX ix_shopping_list_items_position ON shopping_list_items (position);
CREATE INDEX ix_shopping_list_items_shopping_list_id ON shopping_list_items (shopping_list_id);
CREATE INDEX ix_shopping_list_recipe_reference_created_at ON shopping_list_recipe_reference (created_at);
CREATE INDEX ix_tags_created_at ON tags (created_at);
CREATE INDEX ix_tools_created_at ON tools (created_at);
CREATE INDEX ix_tools_group_id ON tools (group_id);
CREATE UNIQUE INDEX ix_groups_slug ON groups (slug);
CREATE INDEX ix_tools_name ON tools (name);
CREATE INDEX ix_tools_slug ON tools (slug);
CREATE TABLE "cookbooks_to_categories" (
	cookbook_id CHAR(32), 
	category_id CHAR(32), 
	CONSTRAINT cookbook_id_category_id_key UNIQUE (cookbook_id, category_id), 
	FOREIGN KEY(cookbook_id) REFERENCES cookbooks (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);
CREATE INDEX ix_cookbooks_to_categories_cookbook_id ON cookbooks_to_categories (cookbook_id);
CREATE INDEX ix_cookbooks_to_categories_category_id ON cookbooks_to_categories (category_id);
CREATE TABLE "cookbooks_to_tags" (
	cookbook_id CHAR(32), 
	tag_id CHAR(32), 
	CONSTRAINT cookbook_id_tag_id_key UNIQUE (cookbook_id, tag_id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id), 
	FOREIGN KEY(cookbook_id) REFERENCES cookbooks (id)
);
CREATE INDEX ix_cookbooks_to_tags_tag_id ON cookbooks_to_tags (tag_id);
CREATE INDEX ix_cookbooks_to_tags_cookbook_id ON cookbooks_to_tags (cookbook_id);
CREATE TABLE "cookbooks_to_tools" (
	cookbook_id CHAR(32), 
	tool_id CHAR(32), 
	CONSTRAINT cookbook_id_tool_id_key UNIQUE (cookbook_id, tool_id), 
	FOREIGN KEY(tool_id) REFERENCES tools (id), 
	FOREIGN KEY(cookbook_id) REFERENCES cookbooks (id)
);
CREATE INDEX ix_cookbooks_to_tools_cookbook_id ON cookbooks_to_tools (cookbook_id);
CREATE INDEX ix_cookbooks_to_tools_tool_id ON cookbooks_to_tools (tool_id);
CREATE TABLE "group_to_categories" (
	group_id CHAR(32), 
	category_id CHAR(32), 
	CONSTRAINT group_id_category_id_key UNIQUE (group_id, category_id), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_group_to_categories_category_id ON group_to_categories (category_id);
CREATE INDEX ix_group_to_categories_group_id ON group_to_categories (group_id);
CREATE TABLE "plan_rules_to_categories" (
	group_plan_rule_id CHAR(32), 
	category_id CHAR(32), 
	CONSTRAINT group_plan_rule_id_category_id_key UNIQUE (group_plan_rule_id, category_id), 
	FOREIGN KEY(group_plan_rule_id) REFERENCES group_meal_plan_rules (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);
CREATE INDEX ix_plan_rules_to_categories_category_id ON plan_rules_to_categories (category_id);
CREATE INDEX ix_plan_rules_to_categories_group_plan_rule_id ON plan_rules_to_categories (group_plan_rule_id);
CREATE TABLE "plan_rules_to_tags" (
	plan_rule_id CHAR(32), 
	tag_id CHAR(32), 
	CONSTRAINT plan_rule_id_tag_id_key UNIQUE (plan_rule_id, tag_id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id), 
	FOREIGN KEY(plan_rule_id) REFERENCES group_meal_plan_rules (id)
);
CREATE INDEX ix_plan_rules_to_tags_plan_rule_id ON plan_rules_to_tags (plan_rule_id);
CREATE INDEX ix_plan_rules_to_tags_tag_id ON plan_rules_to_tags (tag_id);
CREATE TABLE "recipes_to_categories" (
	recipe_id CHAR(32), 
	category_id CHAR(32), 
	CONSTRAINT recipe_id_category_id_key UNIQUE (recipe_id, category_id), 
	FOREIGN KEY(category_id) REFERENCES categories (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE INDEX ix_recipes_to_categories_category_id ON recipes_to_categories (category_id);
CREATE INDEX ix_recipes_to_categories_recipe_id ON recipes_to_categories (recipe_id);
CREATE TABLE "recipes_to_tags" (
	recipe_id CHAR(32), 
	tag_id CHAR(32), 
	CONSTRAINT recipe_id_tag_id_key UNIQUE (recipe_id, tag_id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(tag_id) REFERENCES tags (id)
);
CREATE INDEX ix_recipes_to_tags_tag_id ON recipes_to_tags (tag_id);
CREATE INDEX ix_recipes_to_tags_recipe_id ON recipes_to_tags (recipe_id);
CREATE TABLE "recipes_to_tools" (
	recipe_id CHAR(32), 
	tool_id CHAR(32), 
	CONSTRAINT recipe_id_tool_id_key UNIQUE (recipe_id, tool_id), 
	FOREIGN KEY(tool_id) REFERENCES tools (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE INDEX ix_recipes_to_tools_recipe_id ON recipes_to_tools (recipe_id);
CREATE INDEX ix_recipes_to_tools_tool_id ON recipes_to_tools (tool_id);
CREATE TABLE "shopping_lists_multi_purpose_labels" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	shopping_list_id CHAR(32) NOT NULL, 
	label_id CHAR(32) NOT NULL, 
	position INTEGER NOT NULL, 
	PRIMARY KEY (id, shopping_list_id, label_id), 
	CONSTRAINT shopping_list_id_label_id_key UNIQUE (shopping_list_id, label_id), 
	FOREIGN KEY(shopping_list_id) REFERENCES shopping_lists (id), 
	FOREIGN KEY(label_id) REFERENCES multi_purpose_labels (id)
);
CREATE TABLE "ingredient_units" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	name VARCHAR, 
	description VARCHAR, 
	abbreviation VARCHAR, 
	fraction BOOLEAN, 
	use_abbreviation BOOLEAN, 
	name_normalized VARCHAR, 
	abbreviation_normalized VARCHAR, plural_name VARCHAR, plural_name_normalized VARCHAR, plural_abbreviation VARCHAR, plural_abbreviation_normalized VARCHAR, standard_quantity FLOAT, standard_unit VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT ingredient_units_name_group_id_key UNIQUE (name, group_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_ingredient_units_group_id ON ingredient_units (group_id);
CREATE INDEX ix_ingredient_units_abbreviation_normalized ON ingredient_units (abbreviation_normalized);
CREATE INDEX ix_ingredient_units_name_normalized ON ingredient_units (name_normalized);
CREATE INDEX ix_ingredient_units_created_at ON ingredient_units (created_at);
CREATE TABLE "multi_purpose_labels" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	name VARCHAR(255) NOT NULL, 
	color VARCHAR(10) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT multi_purpose_labels_name_group_id_key UNIQUE (name, group_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_multi_purpose_labels_group_id ON multi_purpose_labels (group_id);
CREATE INDEX ix_multi_purpose_labels_created_at ON multi_purpose_labels (created_at);
CREATE INDEX ix_shopping_lists_multi_purpose_labels_created_at ON shopping_lists_multi_purpose_labels (created_at);
CREATE TABLE ingredient_units_aliases (
	id CHAR(32) NOT NULL, 
	unit_id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	name_normalized VARCHAR, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id, unit_id), 
	FOREIGN KEY(unit_id) REFERENCES ingredient_units (id)
);
CREATE INDEX ix_ingredient_units_aliases_created_at ON ingredient_units_aliases (created_at);
CREATE INDEX ix_ingredient_units_aliases_name_normalized ON ingredient_units_aliases (name_normalized);
CREATE TABLE ingredient_foods_aliases (
	id CHAR(32) NOT NULL, 
	food_id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	name_normalized VARCHAR, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id, food_id), 
	FOREIGN KEY(food_id) REFERENCES ingredient_foods (id)
);
CREATE INDEX ix_ingredient_foods_aliases_created_at ON ingredient_foods_aliases (created_at);
CREATE INDEX ix_ingredient_foods_aliases_name_normalized ON ingredient_foods_aliases (name_normalized);
CREATE INDEX ix_ingredient_units_plural_name_normalized ON ingredient_units (plural_name_normalized);
CREATE INDEX ix_ingredient_units_plural_abbreviation_normalized ON ingredient_units (plural_abbreviation_normalized);
CREATE TABLE "shopping_lists" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	name VARCHAR, 
	user_id CHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_user_shopping_lists FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_shopping_lists_created_at ON shopping_lists (created_at);
CREATE INDEX ix_shopping_lists_group_id ON shopping_lists (group_id);
CREATE INDEX ix_shopping_lists_user_id ON shopping_lists (user_id);
CREATE TABLE users_to_recipes (
	user_id CHAR(32) NOT NULL, 
	recipe_id CHAR(32) NOT NULL, 
	rating FLOAT, 
	is_favorite BOOLEAN NOT NULL, 
	id CHAR(32) NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (user_id, recipe_id, id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	CONSTRAINT user_id_recipe_id_rating_key UNIQUE (user_id, recipe_id)
);
CREATE INDEX ix_users_to_recipes_created_at ON users_to_recipes (created_at);
CREATE INDEX ix_users_to_recipes_is_favorite ON users_to_recipes (is_favorite);
CREATE INDEX ix_users_to_recipes_rating ON users_to_recipes (rating);
CREATE INDEX ix_users_to_recipes_recipe_id ON users_to_recipes (recipe_id);
CREATE INDEX ix_users_to_recipes_user_id ON users_to_recipes (user_id);
CREATE TABLE "recipes" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	slug VARCHAR, 
	group_id CHAR(32) NOT NULL, 
	user_id CHAR(32), 
	name VARCHAR NOT NULL, 
	description VARCHAR, 
	image VARCHAR, 
	total_time VARCHAR, 
	prep_time VARCHAR, 
	perform_time VARCHAR, 
	cook_time VARCHAR, 
	recipe_yield VARCHAR, 
	"recipeCuisine" VARCHAR, 
	rating FLOAT, 
	org_url VARCHAR, 
	date_added DATE, 
	date_updated DATETIME, 
	is_ocr_recipe BOOLEAN, 
	last_made DATETIME, 
	name_normalized VARCHAR NOT NULL, 
	description_normalized VARCHAR, recipe_yield_quantity FLOAT DEFAULT '0' NOT NULL, recipe_servings FLOAT DEFAULT '0' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT recipe_slug_group_id_key UNIQUE (slug, group_id), 
	FOREIGN KEY(user_id) REFERENCES users (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_recipes_description_normalized ON recipes (description_normalized);
CREATE INDEX ix_recipes_slug ON recipes (slug);
CREATE INDEX ix_recipes_group_id ON recipes (group_id);
CREATE INDEX ix_recipes_user_id ON recipes (user_id);
CREATE INDEX ix_recipes_name_normalized ON recipes (name_normalized);
CREATE INDEX ix_recipes_created_at ON recipes (created_at);
CREATE INDEX ix_recipes_rating ON recipes (rating);
CREATE TABLE "ingredient_foods" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	name VARCHAR, 
	description VARCHAR, 
	label_id CHAR(32), 
	name_normalized VARCHAR, 
	plural_name VARCHAR, 
	plural_name_normalized VARCHAR, 
	on_hand BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ingredient_foods_name_group_id_key UNIQUE (name, group_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	FOREIGN KEY(label_id) REFERENCES multi_purpose_labels (id)
);
CREATE INDEX ix_ingredient_foods_name_normalized ON ingredient_foods (name_normalized);
CREATE INDEX ix_ingredient_foods_label_id ON ingredient_foods (label_id);
CREATE INDEX ix_ingredient_foods_group_id ON ingredient_foods (group_id);
CREATE INDEX ix_ingredient_foods_plural_name_normalized ON ingredient_foods (plural_name_normalized);
CREATE INDEX ix_ingredient_foods_created_at ON ingredient_foods (created_at);
CREATE TABLE households (
	id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	slug VARCHAR, 
	group_id CHAR(32) NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	CONSTRAINT household_name_group_id_key UNIQUE (group_id, name), 
	CONSTRAINT household_slug_group_id_key UNIQUE (group_id, slug)
);
CREATE INDEX ix_households_created_at ON households (created_at);
CREATE INDEX ix_households_group_id ON households (group_id);
CREATE INDEX ix_households_name ON households (name);
CREATE INDEX ix_households_slug ON households (slug);
CREATE TABLE "cookbooks" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	position INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	slug VARCHAR NOT NULL, 
	description VARCHAR, 
	group_id CHAR(32), 
	public BOOLEAN, 
	require_all_categories BOOLEAN, 
	require_all_tags BOOLEAN, 
	require_all_tools BOOLEAN, 
	household_id CHAR(32), query_filter_string VARCHAR DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_cookbooks_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	CONSTRAINT cookbook_slug_group_id_key UNIQUE (slug, group_id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_cookbooks_group_id ON cookbooks (group_id);
CREATE INDEX ix_cookbooks_created_at ON cookbooks (created_at);
CREATE INDEX ix_cookbooks_slug ON cookbooks (slug);
CREATE INDEX ix_cookbooks_household_id ON cookbooks (household_id);
CREATE TABLE "group_events_notifiers" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	apprise_url VARCHAR NOT NULL, 
	group_id CHAR(32), 
	household_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_group_events_notifiers_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_group_events_notifiers_group_id ON group_events_notifiers (group_id);
CREATE INDEX ix_group_events_notifiers_created_at ON group_events_notifiers (created_at);
CREATE INDEX ix_group_events_notifiers_household_id ON group_events_notifiers (household_id);
CREATE TABLE "group_meal_plan_rules" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	day VARCHAR NOT NULL, 
	entry_type VARCHAR NOT NULL, 
	household_id CHAR(32), query_filter_string VARCHAR DEFAULT '' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_group_meal_plan_rules_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_group_meal_plan_rules_group_id ON group_meal_plan_rules (group_id);
CREATE INDEX ix_group_meal_plan_rules_created_at ON group_meal_plan_rules (created_at);
CREATE INDEX ix_group_meal_plan_rules_household_id ON group_meal_plan_rules (household_id);
CREATE TABLE "invite_tokens" (
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	token VARCHAR NOT NULL, 
	uses_left INTEGER NOT NULL, 
	group_id CHAR(32), 
	household_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_invite_tokens_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_invite_tokens_created_at ON invite_tokens (created_at);
CREATE UNIQUE INDEX ix_invite_tokens_token ON invite_tokens (token);
CREATE INDEX ix_invite_tokens_group_id ON invite_tokens (group_id);
CREATE INDEX ix_invite_tokens_household_id ON invite_tokens (household_id);
CREATE TABLE "recipe_actions" (
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	action_type VARCHAR NOT NULL, 
	title VARCHAR NOT NULL, 
	url VARCHAR NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	household_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_recipe_actions_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_recipe_actions_title ON recipe_actions (title);
CREATE INDEX ix_recipe_actions_action_type ON recipe_actions (action_type);
CREATE INDEX ix_recipe_actions_created_at ON recipe_actions (created_at);
CREATE INDEX ix_recipe_actions_group_id ON recipe_actions (group_id);
CREATE INDEX ix_recipe_actions_household_id ON recipe_actions (household_id);
CREATE TABLE "webhook_urls" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32), 
	enabled BOOLEAN, 
	name VARCHAR, 
	url VARCHAR, 
	time VARCHAR, 
	webhook_type VARCHAR, 
	scheduled_time TIME, 
	household_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_webhook_urls_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_webhook_urls_group_id ON webhook_urls (group_id);
CREATE INDEX ix_webhook_urls_created_at ON webhook_urls (created_at);
CREATE INDEX ix_webhook_urls_household_id ON webhook_urls (household_id);
CREATE TABLE plan_rules_to_households (
	group_plan_rule_id CHAR(32), 
	household_id CHAR(32), 
	FOREIGN KEY(group_plan_rule_id) REFERENCES group_meal_plan_rules (id), 
	FOREIGN KEY(household_id) REFERENCES households (id), 
	CONSTRAINT group_plan_rule_id_household_id_key UNIQUE (group_plan_rule_id, household_id)
);
CREATE INDEX ix_plan_rules_to_households_group_plan_rule_id ON plan_rules_to_households (group_plan_rule_id);
CREATE INDEX ix_plan_rules_to_households_household_id ON plan_rules_to_households (household_id);
CREATE INDEX ix_recipes_recipe_yield_quantity ON recipes (recipe_yield_quantity);
CREATE INDEX ix_recipes_recipe_servings ON recipes (recipe_servings);
CREATE TABLE households_to_recipes (
	id CHAR(32) NOT NULL, 
	household_id CHAR(32) NOT NULL, 
	recipe_id CHAR(32) NOT NULL, 
	last_made DATETIME, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id, household_id, recipe_id), 
	FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id), 
	CONSTRAINT household_id_recipe_id_key UNIQUE (household_id, recipe_id)
);
CREATE INDEX ix_households_to_recipes_created_at ON households_to_recipes (created_at);
CREATE INDEX ix_households_to_recipes_household_id ON households_to_recipes (household_id);
CREATE INDEX ix_households_to_recipes_recipe_id ON households_to_recipes (recipe_id);
CREATE TABLE households_to_tools (
	household_id CHAR(32), 
	tool_id CHAR(32), 
	FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(tool_id) REFERENCES tools (id), 
	CONSTRAINT household_id_tool_id_key UNIQUE (household_id, tool_id)
);
CREATE INDEX ix_households_to_tools_household_id ON households_to_tools (household_id);
CREATE INDEX ix_households_to_tools_tool_id ON households_to_tools (tool_id);
CREATE TABLE households_to_ingredient_foods (
	household_id CHAR(32), 
	food_id CHAR(32), 
	FOREIGN KEY(food_id) REFERENCES ingredient_foods (id), 
	FOREIGN KEY(household_id) REFERENCES households (id), 
	CONSTRAINT household_id_food_id_key UNIQUE (household_id, food_id)
);
CREATE INDEX ix_households_to_ingredient_foods_food_id ON households_to_ingredient_foods (food_id);
CREATE INDEX ix_households_to_ingredient_foods_household_id ON households_to_ingredient_foods (household_id);
CREATE TABLE "recipes_ingredients" (
	created_at DATETIME, 
	update_at DATETIME, 
	id INTEGER NOT NULL, 
	position INTEGER, 
	recipe_id CHAR(32), 
	title VARCHAR, 
	note VARCHAR, 
	unit_id CHAR(32), 
	food_id CHAR(32), 
	quantity INTEGER, 
	reference_id CHAR(32), 
	original_text VARCHAR, 
	note_normalized VARCHAR, 
	original_text_normalized VARCHAR, 
	referenced_recipe_id CHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT fk_recipe_subrecipe FOREIGN KEY(referenced_recipe_id) REFERENCES recipes (id), 
	FOREIGN KEY(unit_id) REFERENCES ingredient_units (id), 
	FOREIGN KEY(food_id) REFERENCES ingredient_foods (id), 
	FOREIGN KEY(recipe_id) REFERENCES recipes (id)
);
CREATE INDEX ix_recipes_ingredients_created_at ON recipes_ingredients (created_at);
CREATE INDEX ix_recipes_ingredients_original_text_normalized ON recipes_ingredients (original_text_normalized);
CREATE INDEX ix_recipes_ingredients_food_id ON recipes_ingredients (food_id);
CREATE INDEX ix_recipes_ingredients_position ON recipes_ingredients (position);
CREATE INDEX ix_recipes_ingredients_note_normalized ON recipes_ingredients (note_normalized);
CREATE INDEX ix_recipes_ingredients_unit_id ON recipes_ingredients (unit_id);
CREATE INDEX ix_recipes_ingredients_referenced_recipe_id ON recipes_ingredients (referenced_recipe_id);
CREATE TABLE "group_events_notifier_options" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	event_notifier_id CHAR(32) NOT NULL, 
	recipe_created BOOLEAN NOT NULL, 
	recipe_updated BOOLEAN NOT NULL, 
	recipe_deleted BOOLEAN NOT NULL, 
	user_signup BOOLEAN NOT NULL, 
	data_migrations BOOLEAN NOT NULL, 
	data_export BOOLEAN NOT NULL, 
	data_import BOOLEAN NOT NULL, 
	mealplan_entry_created BOOLEAN NOT NULL, 
	shopping_list_created BOOLEAN NOT NULL, 
	shopping_list_updated BOOLEAN NOT NULL, 
	shopping_list_deleted BOOLEAN NOT NULL, 
	cookbook_created BOOLEAN NOT NULL, 
	cookbook_updated BOOLEAN NOT NULL, 
	cookbook_deleted BOOLEAN NOT NULL, 
	tag_created BOOLEAN NOT NULL, 
	tag_updated BOOLEAN NOT NULL, 
	tag_deleted BOOLEAN NOT NULL, 
	category_created BOOLEAN NOT NULL, 
	category_updated BOOLEAN NOT NULL, 
	category_deleted BOOLEAN NOT NULL, 
	label_created BOOLEAN DEFAULT 0 NOT NULL, 
	label_updated BOOLEAN DEFAULT 0 NOT NULL, 
	label_deleted BOOLEAN DEFAULT 0 NOT NULL, 
	mealplan_entry_updated BOOLEAN DEFAULT 0 NOT NULL, 
	mealplan_entry_deleted BOOLEAN DEFAULT 0 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(event_notifier_id) REFERENCES group_events_notifiers (id)
);
CREATE INDEX ix_group_events_notifier_options_created_at ON group_events_notifier_options (created_at);
CREATE TABLE "group_preferences" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	private_group BOOLEAN, 
	first_day_of_week INTEGER, 
	recipe_public BOOLEAN, 
	recipe_show_nutrition BOOLEAN, 
	recipe_show_assets BOOLEAN, 
	recipe_landscape_view BOOLEAN, 
	recipe_disable_comments BOOLEAN, 
	recipe_disable_amount BOOLEAN, 
	show_announcements BOOLEAN DEFAULT 1 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id)
);
CREATE INDEX ix_group_preferences_group_id ON group_preferences (group_id);
CREATE INDEX ix_group_preferences_created_at ON group_preferences (created_at);
CREATE TABLE "household_preferences" (
	id CHAR(32) NOT NULL, 
	household_id CHAR(32) NOT NULL, 
	private_household BOOLEAN, 
	first_day_of_week INTEGER, 
	recipe_public BOOLEAN, 
	recipe_show_nutrition BOOLEAN, 
	recipe_show_assets BOOLEAN, 
	recipe_landscape_view BOOLEAN, 
	recipe_disable_comments BOOLEAN, 
	recipe_disable_amount BOOLEAN, 
	created_at DATETIME, 
	update_at DATETIME, 
	lock_recipe_edits_from_other_households BOOLEAN, 
	show_announcements BOOLEAN DEFAULT 1 NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(household_id) REFERENCES households (id)
);
CREATE INDEX ix_household_preferences_created_at ON household_preferences (created_at);
CREATE INDEX ix_household_preferences_household_id ON household_preferences (household_id);
CREATE TABLE "users" (
	created_at DATETIME, 
	update_at DATETIME, 
	id CHAR(32) NOT NULL, 
	full_name VARCHAR, 
	username VARCHAR, 
	email VARCHAR, 
	password VARCHAR, 
	admin BOOLEAN, 
	advanced BOOLEAN, 
	group_id CHAR(32) NOT NULL, 
	cache_key VARCHAR, 
	can_manage BOOLEAN, 
	can_invite BOOLEAN, 
	can_organize BOOLEAN, 
	owned_recipes_id CHAR(32), 
	login_attemps INTEGER, 
	locked_at DATETIME, 
	auth_method VARCHAR(6) DEFAULT 'MEALIE' NOT NULL, 
	household_id CHAR(32), 
	can_manage_household BOOLEAN, 
	show_announcements BOOLEAN DEFAULT 1 NOT NULL, 
	last_read_announcement VARCHAR, tokens_valid_after DATETIME, external_avatar_hash VARCHAR, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_users_household_id FOREIGN KEY(household_id) REFERENCES households (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	FOREIGN KEY(owned_recipes_id) REFERENCES recipes (id)
);
CREATE INDEX ix_users_group_id ON users (group_id);
CREATE INDEX ix_users_created_at ON users (created_at);
CREATE UNIQUE INDEX ix_users_email ON users (email);
CREATE INDEX ix_users_household_id ON users (household_id);
CREATE INDEX ix_users_full_name ON users (full_name);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE TABLE ai_provider_settings (
	id CHAR(32) NOT NULL, 
	group_id CHAR(32) NOT NULL, 
	default_provider_id CHAR(32), 
	audio_provider_id CHAR(32), 
	image_provider_id CHAR(32), 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(default_provider_id) REFERENCES ai_providers (id), 
	FOREIGN KEY(audio_provider_id) REFERENCES ai_providers (id), 
	FOREIGN KEY(group_id) REFERENCES groups (id), 
	FOREIGN KEY(image_provider_id) REFERENCES ai_providers (id), 
	CONSTRAINT ai_provider_settings_group_id_key UNIQUE (group_id)
);
CREATE INDEX ix_ai_provider_settings_default_provider_id ON ai_provider_settings (default_provider_id);
CREATE INDEX ix_ai_provider_settings_audio_provider_id ON ai_provider_settings (audio_provider_id);
CREATE INDEX ix_ai_provider_settings_created_at ON ai_provider_settings (created_at);
CREATE INDEX ix_ai_provider_settings_group_id ON ai_provider_settings (group_id);
CREATE INDEX ix_ai_provider_settings_image_provider_id ON ai_provider_settings (image_provider_id);
CREATE TABLE ai_providers (
	id CHAR(32) NOT NULL, 
	settings_id CHAR(32) NOT NULL, 
	name VARCHAR NOT NULL, 
	base_url VARCHAR, 
	api_key VARCHAR NOT NULL, 
	model VARCHAR NOT NULL, 
	timeout INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(settings_id) REFERENCES ai_provider_settings (id), 
	CONSTRAINT ai_providers_name_settings_id_key UNIQUE (name, settings_id)
);
CREATE INDEX ix_ai_providers_created_at ON ai_providers (created_at);
CREATE INDEX ix_ai_providers_name ON ai_providers (name);
CREATE INDEX ix_ai_providers_settings_id ON ai_providers (settings_id);
CREATE TABLE ai_provider_headers (
	provider_id CHAR(32) NOT NULL, 
	id INTEGER NOT NULL, 
	key_name VARCHAR, 
	value VARCHAR, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_id) REFERENCES ai_providers (id)
);
CREATE INDEX ix_ai_provider_headers_created_at ON ai_provider_headers (created_at);
CREATE INDEX ix_ai_provider_headers_provider_id ON ai_provider_headers (provider_id);
CREATE TABLE ai_provider_params (
	provider_id CHAR(32) NOT NULL, 
	id INTEGER NOT NULL, 
	key_name VARCHAR, 
	value VARCHAR, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(provider_id) REFERENCES ai_providers (id)
);
CREATE INDEX ix_ai_provider_params_created_at ON ai_provider_params (created_at);
CREATE INDEX ix_ai_provider_params_provider_id ON ai_provider_params (provider_id);
CREATE TABLE ingredient_foods_substitutions (
	id CHAR(32) NOT NULL, 
	food_id CHAR(32) NOT NULL, 
	substitute_food_id CHAR(32), 
	note VARCHAR, 
	position INTEGER, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT ingredient_foods_substitutions_no_self_substitution CHECK (food_id != substitute_food_id), 
	CONSTRAINT ingredient_foods_substitutions_food_or_note CHECK (substitute_food_id IS NOT NULL OR note IS NOT NULL), 
	FOREIGN KEY(food_id) REFERENCES ingredient_foods (id), 
	FOREIGN KEY(substitute_food_id) REFERENCES ingredient_foods (id), 
	CONSTRAINT ingredient_foods_substitutions_food_ids_key UNIQUE (food_id, substitute_food_id)
);
CREATE INDEX ix_ingredient_foods_substitutions_created_at ON ingredient_foods_substitutions (created_at);
CREATE INDEX ix_ingredient_foods_substitutions_food_id ON ingredient_foods_substitutions (food_id);
CREATE INDEX ix_ingredient_foods_substitutions_position ON ingredient_foods_substitutions (position);
CREATE INDEX ix_ingredient_foods_substitutions_substitute_food_id ON ingredient_foods_substitutions (substitute_food_id);
CREATE TABLE recipes_ingredients_substitutions (
	id CHAR(32) NOT NULL, 
	ingredient_id INTEGER NOT NULL, 
	substitute_food_id CHAR(32), 
	note VARCHAR, 
	position INTEGER, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT recipes_ingredients_substitutions_food_or_note CHECK (substitute_food_id IS NOT NULL OR note IS NOT NULL), 
	FOREIGN KEY(ingredient_id) REFERENCES recipes_ingredients (id), 
	FOREIGN KEY(substitute_food_id) REFERENCES ingredient_foods (id)
);
CREATE INDEX ix_recipes_ingredients_substitutions_created_at ON recipes_ingredients_substitutions (created_at);
CREATE INDEX ix_recipes_ingredients_substitutions_ingredient_id ON recipes_ingredients_substitutions (ingredient_id);
CREATE INDEX ix_recipes_ingredients_substitutions_position ON recipes_ingredients_substitutions (position);
CREATE INDEX ix_recipes_ingredients_substitutions_substitute_food_id ON recipes_ingredients_substitutions (substitute_food_id);
CREATE TABLE recipe_note_ref_link (
	instruction_id CHAR(32), 
	reference_id CHAR(32), 
	id INTEGER NOT NULL, 
	created_at DATETIME, 
	update_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(instruction_id) REFERENCES recipe_instructions (id)
);
CREATE INDEX ix_recipe_note_ref_link_created_at ON recipe_note_ref_link (created_at);
CREATE INDEX ix_recipe_note_ref_link_instruction_id ON recipe_note_ref_link (instruction_id);
CREATE INDEX ix_recipe_note_ref_link_reference_id ON recipe_note_ref_link (reference_id);
CREATE INDEX ix_notes_reference_id ON notes (reference_id);
