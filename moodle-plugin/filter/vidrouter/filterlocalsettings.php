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
 * Per-context (course, category, activity) overrides for filter_vidrouter
 *
 * Loaded by core (filter/manage.php) when the Settings link is used on the Filters page. An empty value
 * means "inherit" and is removed from filter_config by the base class save_changes(). Inheritance down
 * the context tree is resolved by video_renderer::overrides_for(), as core does not do it.
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

class vidrouter_filter_local_settings_form extends filter_local_settings_form {
    #[\Override]
    protected function definition_inner($mform) {
        $inherit = ['' => get_string('usesitedefault', 'filter_vidrouter')];

        $mform->addElement('static', 'intro', '', get_string('localsettings_intro', 'filter_vidrouter'));

        $sources = [
            'youtube' => get_string('source_youtube', 'filter_vidrouter'),
            'collegeramaid' => get_string('source_collegerama', 'filter_vidrouter'),
        ];

        $mform->addElement('select', 'primarysource', get_string('primarysource', 'filter_vidrouter'), $inherit + $sources);
        $mform->addElement('select', 'fallbacksource', get_string('fallbacksource', 'filter_vidrouter'), $inherit + $sources);

        $mform->addElement('select', 'embedstyle', get_string('embedstyle', 'filter_vidrouter'), $inherit + [
            'video' => get_string('embedstyle_video', 'filter_vidrouter'),
            'iframe' => get_string('embedstyle_iframe', 'filter_vidrouter'),
        ]);
    }

    #[\Override]
    public function save_changes($data) {
        $data = array_intersect_key((array) $data, array_flip(\filter_vidrouter\video_renderer::OVERRIDABLE));
        parent::save_changes((object) $data);
        \filter_vidrouter\video_renderer::reset_caches();
    }
}
