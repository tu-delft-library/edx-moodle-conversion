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
 * Admin settings for filter_vidrouter
 *
 * Included automatically by core (lib/classes/plugininfo/filter.php) into
 * Site administration > Plugins > Filters > Video Router Filter — $settings
 * is already a bound admin_settingpage by the time this file runs.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

if ($ADMIN->fulltree) {
    $settings->add(new admin_setting_configselect(
        'filter_vidrouter/primarysource',
        get_string('primarysource', 'filter_vidrouter'),
        get_string('primarysource_desc', 'filter_vidrouter'),
        'youtube',
        [
            'youtube' => get_string('source_youtube', 'filter_vidrouter'),
        ]
    ));

    $settings->add(new admin_setting_configselect(
        'filter_vidrouter/embedstyle',
        get_string('embedstyle', 'filter_vidrouter'),
        get_string('embedstyle_desc', 'filter_vidrouter'),
        'iframe',
        [
            'video' => get_string('embedstyle_video', 'filter_vidrouter'),
            'iframe' => get_string('embedstyle_iframe', 'filter_vidrouter'),
        ]
    ));
}

$ADMIN->add($parentnodename, new admin_externalpage(
    'filter_vidrouter_manage',
    get_string('manage', 'filter_vidrouter'),
    new moodle_url('/filter/vidrouter/manage.php'),
    'filter/vidrouter:manage'
));
