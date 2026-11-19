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
 * Admin settings.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) {
    $settings = new admin_settingpage('local_linearnav', new lang_string('pluginname', 'local_linearnav'));
    $settings->add(new \local_linearnav\admin_setting_checkbox(
        'local_linearnav/skiplinked',
        new lang_string('skiplinked', 'local_linearnav'),
        new lang_string('skiplinked_desc', 'local_linearnav'),
        0
    ));
    $settings->add(new \local_linearnav\admin_setting_checkbox(
        'local_linearnav/includesections',
        new lang_string('includesections', 'local_linearnav'),
        new lang_string('includesections_desc', 'local_linearnav'),
        1
    ));
    foreach (['includetopsections', 'includesubsections'] as $name) {
        $settings->add(new \local_linearnav\admin_setting_checkbox(
            'local_linearnav/' . $name,
            new lang_string($name, 'local_linearnav'),
            new lang_string($name . '_desc', 'local_linearnav'),
            0
        ));
        $settings->hide_if('local_linearnav/' . $name, 'local_linearnav/includesections', 'notchecked');
    }
    $ADMIN->add('localplugins', $settings);
}
