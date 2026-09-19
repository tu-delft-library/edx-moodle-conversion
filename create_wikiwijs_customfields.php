<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle.  If not, see <http://www.gnu.org/licenses/>.

/**
 * One-off registration script for the Wikiwijs metadata custom field category.
 *
 * Not a plugin — copy this file into the target Moodle site's admin/cli/ directory
 * and run once per instance:
 *
 *   php admin/cli/create_wikiwijs_customfields.php
 *
 * Registers the 'Wikiwijs metadata' course customfield category and its fields.
 * `ocw` (the OLX -> Moodle converter) only auto-populates 5 of these fields on
 * conversion (publisher/language/access/license/summary, all 'text' type — see
 * PLAN.md §9.2 for why these are 'text' and not 'select': a select field's backed-up
 * value is an option-list index, not the string, so a shortname+type mismatch
 * against a 'select' registration would silently never match on restore). The
 * remaining fields are registered for manual entry in the Moodle UI after
 * restore and are never written by `ocw`.
 *
 * Idempotent: re-running skips any shortname that's already registered under
 * the category, so it's safe to re-run after adding new fields to $fields below.
 *
 * @package    local_owc_metadata
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

define('CLI_SCRIPT', true);

require(__DIR__ . '/../../config.php');
require_once($CFG->libdir . '/clilib.php');

$handler = \core_course\customfield\course_handler::create();

$categoryname = 'Metadata Edusources';
$oldcategoryname = 'Wikiwijs metadata';
$category = null;
foreach ($handler->get_categories_with_fields() as $existing) {
    if ($existing->get('name') === $categoryname) {
        $category = $existing;
        break;
    }
    if ($existing->get('name') === $oldcategoryname) {
        $category = $existing;
        break;
    }
}
if ($category === null) {
    $categoryid = $handler->create_category($categoryname);
    $category = \core_customfield\category_controller::create($categoryid);
    cli_writeln("Created customfield category '{$categoryname}' (id {$categoryid}).");
} else if ($category->get('name') !== $categoryname) {
    $category->set('name', $categoryname);
    $category->save();
    cli_writeln("Renamed customfield category '{$oldcategoryname}' -> '{$categoryname}' (id {$category->get('id')}).");
} else {
    cli_writeln("Category '{$categoryname}' already exists (id {$category->get('id')}), reusing it.");
}

$existingshortnames = [];
foreach ($category->get_fields() as $existingfield) {
    $existingshortnames[] = $existingfield->get('shortname');
}

// All fields are 'text' — the manual-entry ones (usable_as/intended_end_user/
// material_type/technical_format) were originally 'select', but their real NL-LOM
// option vocabularies were never saved anywhere durable (only pasted in chat once),
// so a live 'select' just rendered as a permanently empty dropdown. Plain text lets
// someone type the value in by hand until/unless the real vocab gets sourced and
// these get converted back to 'select' with real options.
$fields = [
    ['shortname' => 'publisher', 'name' => 'Publisher / Uitgever', 'type' => 'text'],
    ['shortname' => 'language', 'name' => 'Language / Taal', 'type' => 'text'],
    ['shortname' => 'access', 'name' => 'Access / Toegang', 'type' => 'text'],
    ['shortname' => 'license', 'name' => 'License / Gebruiksrecht', 'type' => 'text'],
    ['shortname' => 'summary', 'name' => 'Summary / Samenvatting', 'type' => 'text'],
    ['shortname' => 'publication_date', 'name' => 'Publication date / Publicatiedatum', 'type' => 'date'],
    ['shortname' => 'usable_as', 'name' => 'Usable as / Bruikbaar als', 'type' => 'text'],
    ['shortname' => 'intended_end_user', 'name' => 'Intended end user / Beoogde eindgebruiker', 'type' => 'text'],
    ['shortname' => 'material_type', 'name' => 'Material type / Soort leermateriaal', 'type' => 'text'],
    ['shortname' => 'technical_format', 'name' => 'Technical format / Technisch formaat', 'type' => 'text'],
    ['shortname' => 'links', 'name' => 'Links', 'type' => 'text'],
    ['shortname' => 'keywords', 'name' => 'Keywords / Trefwoorden', 'type' => 'text'],
    ['shortname' => 'professional_discipline', 'name' => 'Professional discipline / Vakgebied', 'type' => 'text'],
    ['shortname' => 'collection', 'name' => 'Collection / Collectie', 'type' => 'text'],
    ['shortname' => 'faculty', 'name' => 'Faculty / Faculteit', 'type' => 'text'],
    ['shortname' => 'publishing_organization', 'name' => 'Publishing organization / Uitgevende organisatie', 'type' => 'text'],
    ['shortname' => 'education_level', 'name' => 'Education level / Onderwijsniveau', 'type' => 'text'],
];

// Base config keys every field type reads (customfield/classes/field_config_form.php).
// Each field type's own field_controller/data_controller reads additional keys directly
// out of configdata with no isset() guard — missing them doesn't just leave a blank
// default, it throws an ErrorException the moment the field is rendered on any entity
// edit form (course edit settings, in our case). Verified live: 'text' fields crashed
// course/edit.php with "Undefined array key ispassword" until these were added.
$basedefaults = [
    'required' => 0,
    'uniquevalues' => 0,
    'defaultvalue' => '',
    'locked' => 0,
    'visibility' => 2,
];
$typedefaults = [
    'text' => [
        'displaysize' => 50,
        'maxlength' => 1333,
        'ispassword' => 0,
        'link' => '',
        'linktarget' => '',
    ],
    'date' => [
        'mindate' => 0,
        'maxdate' => 0,
        'includetime' => 0,
    ],
];

foreach ($fields as $def) {
    $fulldefaults = $basedefaults + ($typedefaults[$def['type']] ?? []);

    if (in_array($def['shortname'], $existingshortnames, true)) {
        cli_writeln("Skipping '{$def['shortname']}' — already registered.");
        continue;
    }

    $field = \core_customfield\field_controller::create(0, (object) [
        'shortname' => $def['shortname'],
        'name' => $def['name'],
        'type' => $def['type'],
        'configdata' => json_encode($fulldefaults),
    ], $category);
    $field->save();
    cli_writeln("Registered '{$def['shortname']}' ({$def['name']}, {$def['type']}).");
}

cli_writeln('Done.');
