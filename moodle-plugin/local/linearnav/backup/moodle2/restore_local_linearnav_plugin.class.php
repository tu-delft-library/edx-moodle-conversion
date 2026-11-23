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
 * Restore of the per-course overrides.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

/**
 * Restores each <setting> onto the new course.
 */
class restore_local_linearnav_plugin extends restore_local_plugin {
    /**
     * Define the course plugin structure.
     *
     * @return restore_path_element[]
     */
    protected function define_course_plugin_structure() {
        return [new restore_path_element('local_linearnav_setting', $this->get_pathfor('/setting'))];
    }

    /**
     * Store one override, replacing any the target course already has.
     *
     * @param array $data
     */
    public function process_local_linearnav_setting($data) {
        global $DB;

        $courseid = $this->task->get_courseid();
        // Backups from before the split: includesections off turned both section kinds off, on changed nothing.
        if ($data['name'] === 'includesections') {
            $names = $data['value'] === '0' ? ['includetopsections', 'includesubsections'] : [];
        } else {
            $names = [$data['name']];
        }
        foreach ($names as $name) {
            $valid = in_array($name, \local_linearnav\course_settings::NAMES, true)
                && in_array($data['value'], ['0', '1'], true);
            if (!$valid) {
                continue;
            }
            $DB->delete_records('local_linearnav', ['courseid' => $courseid, 'name' => $name]);
            $DB->insert_record('local_linearnav', ['courseid' => $courseid, 'name' => $name, 'value' => $data['value']]);
        }
    }
}
