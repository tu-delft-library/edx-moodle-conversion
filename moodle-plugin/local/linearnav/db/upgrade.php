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
 * Upgrade steps.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

/**
 * Upgrade local_linearnav.
 *
 * @param int $oldversion
 * @return bool
 */
function xmldb_local_linearnav_upgrade($oldversion) {
    global $DB;

    $dbman = $DB->get_manager();

    if ($oldversion < 2026111906) {
        $table = new xmldb_table('local_linearnav');
        $table->add_field('id', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL, XMLDB_SEQUENCE);
        $table->add_field('courseid', XMLDB_TYPE_INTEGER, '10', null, XMLDB_NOTNULL);
        $table->add_field('name', XMLDB_TYPE_CHAR, '50', null, XMLDB_NOTNULL);
        $table->add_field('value', XMLDB_TYPE_CHAR, '10', null, XMLDB_NOTNULL);
        $table->add_key('primary', XMLDB_KEY_PRIMARY, ['id']);
        $table->add_key('courseid', XMLDB_KEY_FOREIGN, ['courseid'], 'course', ['id']);
        $table->add_index('coursename', XMLDB_INDEX_UNIQUE, ['courseid', 'name']);

        if (!$dbman->table_exists($table)) {
            $dbman->create_table($table);
        }

        upgrade_plugin_savepoint(true, 2026111906, 'local', 'linearnav');
    }

    if ($oldversion < 2026112001) {
        if (!get_config('local_linearnav', 'includesections')) {
            set_config('includetopsections', 0, 'local_linearnav');
            set_config('includesubsections', 0, 'local_linearnav');
        }
        unset_config('includesections', 'local_linearnav');
        foreach ($DB->get_records('local_linearnav', ['name' => 'includesections', 'value' => '0']) as $row) {
            foreach (['includetopsections', 'includesubsections'] as $name) {
                $DB->delete_records('local_linearnav', ['courseid' => $row->courseid, 'name' => $name]);
                $DB->insert_record('local_linearnav', ['courseid' => $row->courseid, 'name' => $name, 'value' => '0']);
            }
        }
        $DB->delete_records('local_linearnav', ['name' => 'includesections']);
        upgrade_plugin_savepoint(true, 2026112001, 'local', 'linearnav');
    }

    if ($oldversion < 2026112002) {
        foreach (['prevlabel' => 'previous', 'nextlabel' => 'next'] as $name => $default) {
            $text = get_config('local_linearnav', $name);
            if ($text === '') {
                $text = get_string($default, 'local_linearnav');
            }
            if ($text !== false && !preg_match('/^".*"$/', $text)) {
                set_config($name, '"' . $text . '"', 'local_linearnav');
            }
        }
        upgrade_plugin_savepoint(true, 2026112002, 'local', 'linearnav');
    }

    return true;
}
