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

namespace filter_vidrouter;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/filter/vidrouter/classes/form/edit_form.php');

/**
 * Tests for filter_vidrouter_edit_form
 *
 * @package    filter_vidrouter
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 * @group      filter_vidrouter
 * @covers     \filter_vidrouter_edit_form
 */
final class edit_form_test extends \advanced_testcase {

    private function make_data(array $overrides = []): array {
        return array_merge([
            'vidkey' => 'vid-key_1',
            'title' => 'My Video',
            'courseid' => '2',
            'urlname' => 'my-video',
            'youtubeid' => null,
            'edxvideoid' => null,
            'tuddownloadid' => null,
            'collegeramaid' => null,
            'srtbaseid' => null,
            'videopagepath' => null,
        ], $overrides);
    }

    public function test_validation_accepts_a_valid_vidkey(): void {
        $this->resetAfterTest();

        $form = new \filter_vidrouter_edit_form();
        $errors = $form->validation($this->make_data(['vidkey' => 'Valid_Key-123']), []);

        $this->assertArrayNotHasKey('vidkey', $errors);
    }

    public function test_validation_rejects_a_vidkey_with_spaces(): void {
        $this->resetAfterTest();

        $form = new \filter_vidrouter_edit_form();
        $errors = $form->validation($this->make_data(['vidkey' => 'has a space']), []);

        $this->assertArrayHasKey('vidkey', $errors);
        $this->assertSame(get_string('error_invalid_vidkey', 'filter_vidrouter'), $errors['vidkey']);
    }

    public function test_validation_rejects_a_vidkey_with_special_characters(): void {
        $this->resetAfterTest();

        $form = new \filter_vidrouter_edit_form();
        $errors = $form->validation($this->make_data(['vidkey' => 'bad@key!']), []);

        $this->assertArrayHasKey('vidkey', $errors);
    }

    public function test_validation_rejects_an_empty_vidkey(): void {
        $this->resetAfterTest();

        $form = new \filter_vidrouter_edit_form();
        $errors = $form->validation($this->make_data(['vidkey' => '']), []);

        $this->assertArrayHasKey('vidkey', $errors);
    }
}
