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
    $settings->add(new admin_setting_heading(
        'local_linearnav/disclaimer',
        '',
        new lang_string('disclaimer', 'local_linearnav')
    ));
    $heading = fn(string $name) => $settings->add(new admin_setting_heading(
        'local_linearnav/heading_' . $name,
        new lang_string('heading_' . $name, 'local_linearnav'),
        ''
    ));
    $heading('skipping');
    $settings->add(new \local_linearnav\admin_setting_checkbox(
        'local_linearnav/skiplinked',
        new lang_string('skiplinked', 'local_linearnav'),
        new lang_string('skiplinked_desc', 'local_linearnav'),
        1
    ));
    $settings->add(new \local_linearnav\admin_setting_checkbox(
        'local_linearnav/skiptargets',
        html_writer::tag('em', get_string('skiptargets', 'local_linearnav')),
        new lang_string('skiptargets_desc', 'local_linearnav'),
        0
    ));
    $settings->hide_if('local_linearnav/skiptargets', 'local_linearnav/skiplinked');
    $settings->add(new \local_linearnav\admin_setting_checkbox(
        'local_linearnav/skipfiles',
        new lang_string('skipfiles', 'local_linearnav'),
        new lang_string('skipfiles_desc', 'local_linearnav'),
        0
    ));
    $heading('stops');
    foreach (['includetopsections', 'includesubsections'] as $name) {
        $settings->add(new \local_linearnav\admin_setting_checkbox(
            'local_linearnav/' . $name,
            new lang_string($name, 'local_linearnav'),
            new lang_string($name . '_desc', 'local_linearnav'),
            0
        ));
    }
    $heading('order');
    $settings->add(new admin_setting_configselect(
        'local_linearnav/sectionorder',
        new lang_string('sectionorder', 'local_linearnav'),
        new lang_string('sectionorder_desc', 'local_linearnav'),
        'auto',
        \local_linearnav\course_settings::sectionorder_choices()
    ));
    $heading('buttons');
    foreach (['prevlabel' => 'previous', 'nextlabel' => 'next'] as $name => $default) {
        $settings->add(new admin_setting_configtext(
            'local_linearnav/' . $name,
            new lang_string($name, 'local_linearnav'),
            new lang_string($name . '_desc', 'local_linearnav'),
            '"' . get_string($default, 'local_linearnav') . '"',
            '/^".*"$/'
        ));
    }
    $settings->add(new admin_setting_description(
        'local_linearnav/reset',
        '',
        html_writer::link(
            new moodle_url('/local/linearnav/reset.php'),
            get_string('resetdefaults', 'local_linearnav'),
            ['class' => 'btn btn-secondary mb-4']
        )
    ));
    $ADMIN->add('localplugins', $settings);
}
