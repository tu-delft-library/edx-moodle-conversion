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
 * Backup hook for filter_vidrouter
 *
 * Embeds resolved video HTML into the backup for native backup/restore lifecycle support.
 *
 * @package    filter_vidrouter
 * @copyright  2024 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

class backup_filter_vidrouter_subplugin extends backup_course_plugin {
    /**
     * Define the course plugin structure
     *
     * Returns the XML paths for course-level video data.
     *
     * @return array of backup_path_element
     */
    protected function define_course_plugin_structure() {
        $paths = array();
        $paths[] = new backup_path_element('plugin_filter_vidrouter_course', $this->get_pathfor('/plugin_filter_vidrouter_course'));
        return $paths;
    }
}
