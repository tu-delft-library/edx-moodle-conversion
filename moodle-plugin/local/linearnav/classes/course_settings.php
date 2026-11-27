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
 * Per-course overrides of the site settings, edited on the course settings form.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use core_course\hook\after_form_definition;
use core_course\hook\after_form_submission;
use core_course\hook\before_course_deleted;

/**
 * Course overrides: blank means use the site setting, only overrides are stored.
 */
final class course_settings {
    /** @var array<string, string[]> settings a course can override => their allowed values */
    public const VALUES = [
        'skiplinked' => ['0', '1'],
        'skiptargets' => ['0', '1'],
        'skipfiles' => ['0', '1'],
        'includetopsections' => ['0', '1'],
        'includesubsections' => ['0', '1'],
        'sectionorder' => plan::SECTIONORDERS,
    ];

    /**
     * Labels of the sectionorder values.
     *
     * @return array<string, string> value => label
     */
    public static function sectionorder_choices(): array {
        $choices = [];
        foreach (plan::SECTIONORDERS as $value) {
            $choices[$value] = get_string('sectionorder_' . $value, 'local_linearnav');
        }
        return $choices;
    }

    /**
     * Site config with this course's overrides applied.
     *
     * @param int $courseid
     * @return \stdClass
     */
    public static function for_course(int $courseid): \stdClass {
        $config = get_config('local_linearnav');
        foreach (self::overrides($courseid) as $name => $value) {
            $config->$name = $value;
        }
        return $config;
    }

    /**
     * Stored overrides of a course.
     *
     * @param int $courseid
     * @return array<string, string> name => value
     */
    private static function overrides(int $courseid): array {
        global $DB;

        return $DB->get_records_menu('local_linearnav', ['courseid' => $courseid], '', 'name, value');
    }

    /**
     * Add the override fields to the course settings form.
     *
     * @param after_form_definition $hook
     */
    public static function form_definition(after_form_definition $hook): void {
        $mform = $hook->mform;
        $mform->addElement('header', 'local_linearnav', get_string('pluginname', 'local_linearnav'));
        $default = ['' => get_string('usesitedefault', 'local_linearnav')];
        $yesno = ['1' => get_string('yes'), '0' => get_string('no')];
        $current = self::overrides((int) ($hook->formwrapper->get_course()->id ?? 0));
        foreach (array_keys(self::VALUES) as $name) {
            $field = 'local_linearnav_' . $name;
            $label = get_string($name, 'local_linearnav');
            $options = $default + ($name === 'sectionorder' ? self::sectionorder_choices() : $yesno);
            $mform->addElement('select', $field, $name === 'skiptargets' ? \html_writer::tag('em', $label) : $label, $options);
            $mform->setDefault($field, $current[$name] ?? '');
        }
        $mform->hideIf('local_linearnav_skiptargets', 'local_linearnav_skiplinked', 'eq', '0');
    }

    /**
     * Store the submitted overrides, dropping the blank ones.
     *
     * Core also fires this from update_course() for web services and course uploads, which send none of
     * these fields, so only names present in the data are touched.
     *
     * @param after_form_submission $hook
     */
    public static function form_submission(after_form_submission $hook): void {
        global $DB;

        $data = $hook->get_data();
        foreach (array_keys(self::VALUES) as $name) {
            $field = 'local_linearnav_' . $name;
            if (!property_exists($data, $field)) {
                continue;
            }
            $DB->delete_records('local_linearnav', ['courseid' => $data->id, 'name' => $name]);
            $value = (string) $data->$field;
            if ($value !== '') {
                $DB->insert_record('local_linearnav', ['courseid' => $data->id, 'name' => $name, 'value' => $value]);
            }
        }
    }

    /**
     * Remove a course's overrides with the course.
     *
     * @param before_course_deleted $hook
     */
    public static function course_deleted(before_course_deleted $hook): void {
        global $DB;

        $DB->delete_records('local_linearnav', ['courseid' => $hook->course->id]);
    }
}
