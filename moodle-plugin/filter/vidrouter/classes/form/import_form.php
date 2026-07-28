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
 * Form for bulk-assigning values onto existing video mappings, matched by an existing field
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

require_once($CFG->libdir . '/formslib.php');

class filter_vidrouter_import_form extends moodleform
{
    public function definition()
    {
        $mform = $this->_form;
        $fields = \filter_vidrouter\bulk_import::ASSIGNABLE_FIELDS;
        $options = array_combine($fields, array_map(function ($f) {
            return get_string('form_' . $f, 'filter_vidrouter');
        }, $fields));

        $mform->addElement('select', 'matchfield', get_string('import_matchfield', 'filter_vidrouter'), $options);
        $mform->setDefault('matchfield', 'vidkey');
        $mform->addHelpButton('matchfield', 'import_matchfield', 'filter_vidrouter');

        $mform->addElement(
            'textarea',
            'csvdata',
            get_string('import_csvdata', 'filter_vidrouter'),
            array('rows' => 12, 'cols' => 80)
        );
        $mform->setType('csvdata', PARAM_RAW);
        $mform->addRule('csvdata', get_string('required'), 'required', null, 'client');
        $mform->addHelpButton('csvdata', 'import_csvdata', 'filter_vidrouter');

        $this->add_action_buttons(true, get_string('import_preview', 'filter_vidrouter'));
    }
}
