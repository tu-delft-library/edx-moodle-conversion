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
 * Form for adding/editing video mappings
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

defined('MOODLE_INTERNAL') || die();

require_once($CFG->libdir . '/formslib.php');

class filter_vidrouter_edit_form extends moodleform {

    public function definition() {
        $mform = $this->_form;

        // Video key (required, unique).
        $mform->addElement('text', 'vidkey', get_string('form_vidkey', 'filter_vidrouter'));
        $mform->setType('vidkey', PARAM_TEXT);
        $mform->addRule('vidkey', get_string('required'), 'required', null, 'client');
        $mform->addHelpButton('vidkey', 'form_vidkey', 'filter_vidrouter');
        $mform->addRule('vidkey', get_string('error_invalid_vidkey', 'filter_vidrouter'), 'regex', '/^[A-Za-z0-9_\-]+$/', 'client');

        // Title.
        $mform->addElement('text', 'title', get_string('form_title', 'filter_vidrouter'));
        $mform->setType('title', PARAM_TEXT);
        $mform->addHelpButton('title', 'form_title', 'filter_vidrouter');

        // Course ID.
        $mform->addElement('text', 'courseid', get_string('form_courseid', 'filter_vidrouter'));
        $mform->setType('courseid', PARAM_TEXT);
        $mform->addHelpButton('courseid', 'form_courseid', 'filter_vidrouter');

        // URL name.
        $mform->addElement('text', 'urlname', get_string('form_urlname', 'filter_vidrouter'));
        $mform->setType('urlname', PARAM_TEXT);
        $mform->addHelpButton('urlname', 'form_urlname', 'filter_vidrouter');

        // YouTube ID.
        $mform->addElement('text', 'youtubeid', get_string('form_youtubeid', 'filter_vidrouter'));
        $mform->setType('youtubeid', PARAM_TEXT);
        $mform->addHelpButton('youtubeid', 'form_youtubeid', 'filter_vidrouter');

        // edX Video ID.
        $mform->addElement('text', 'edxvideoid', get_string('form_edxvideoid', 'filter_vidrouter'));
        $mform->setType('edxvideoid', PARAM_TEXT);
        $mform->addHelpButton('edxvideoid', 'form_edxvideoid', 'filter_vidrouter');

        // TU Delft Download ID.
        $mform->addElement('text', 'tuddownloadid', get_string('form_tuddownloadid', 'filter_vidrouter'));
        $mform->setType('tuddownloadid', PARAM_TEXT);
        $mform->addHelpButton('tuddownloadid', 'form_tuddownloadid', 'filter_vidrouter');

        // STL Base ID.
        $mform->addElement('text', 'stlbaseid', get_string('form_stlbaseid', 'filter_vidrouter'));
        $mform->setType('stlbaseid', PARAM_TEXT);
        $mform->addHelpButton('stlbaseid', 'form_stlbaseid', 'filter_vidrouter');

        // Video page path (textarea).
        $mform->addElement('textarea', 'videopagepath', get_string('form_videopagepath', 'filter_vidrouter'));
        $mform->setType('videopagepath', PARAM_RAW);
        $mform->addHelpButton('videopagepath', 'form_videopagepath', 'filter_vidrouter');

        // Action buttons.
        $this->add_action_buttons();
    }

    public function validation($data, $files) {
        $errors = parent::validation($data, $files);

        if (!preg_match('/^[A-Za-z0-9_\-]+$/', $data['vidkey'])) {
            $errors['vidkey'] = get_string('error_invalid_vidkey', 'filter_vidrouter');
        }

        return $errors;
    }
}
