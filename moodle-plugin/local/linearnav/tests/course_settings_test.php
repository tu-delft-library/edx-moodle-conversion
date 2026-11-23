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
 * Course override tests.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use PHPUnit\Framework\Attributes\CoversClass;
use core_course\hook\after_form_submission;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->dirroot . '/course/lib.php');
require_once($CFG->dirroot . '/backup/util/includes/backup_includes.php');
require_once($CFG->dirroot . '/backup/util/includes/restore_includes.php');

/**
 * Course override tests.
 */
#[CoversClass(course_settings::class)]
final class course_settings_test extends \advanced_testcase {
    public function test_submission_stores_only_overrides_and_blank_clears(): void {
        global $DB;

        $this->resetAfterTest();
        set_config('skiplinked', 1, 'local_linearnav');
        $course = $this->getDataGenerator()->create_course();
        $submit = fn(array $data) => course_settings::form_submission(new after_form_submission((object) $data));

        $submit(['id' => $course->id, 'local_linearnav_skiplinked' => '0', 'local_linearnav_includetopsections' => '']);
        $this->assertSame(
            ['skiplinked' => '0'],
            $DB->get_records_menu('local_linearnav', ['courseid' => $course->id], '', 'name, value')
        );
        $this->assertSame('0', course_settings::for_course($course->id)->skiplinked);

        $submit(['id' => $course->id, 'local_linearnav_skiplinked' => '']);
        $this->assertSame(0, $DB->count_records('local_linearnav', ['courseid' => $course->id]));
        $this->assertSame('1', course_settings::for_course($course->id)->skiplinked);
    }

    public function test_course_update_without_form_fields_keeps_overrides(): void {
        global $DB;

        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiplinked', 'value' => '0']);

        update_course((object) ['id' => $course->id, 'fullname' => 'Renamed']);

        $this->assertSame(
            ['skiplinked' => '0'],
            $DB->get_records_menu('local_linearnav', ['courseid' => $course->id], '', 'name, value')
        );
    }

    /**
     * Backup a course and restore it as a new one.
     *
     * @param \stdClass $course
     * @return int new course id
     */
    private function copy(\stdClass $course): int {
        global $USER;

        $bc = new \backup_controller(\backup::TYPE_1COURSE, $course->id, \backup::FORMAT_MOODLE,
            \backup::INTERACTIVE_NO, \backup::MODE_IMPORT, $USER->id);
        $backupid = $bc->get_backupid();
        $bc->execute_plan();
        $bc->destroy();

        $newid = \restore_dbops::create_new_course('Copy', 'copy', $course->category);
        $rc = new \restore_controller($backupid, $newid, \backup::INTERACTIVE_NO, \backup::MODE_IMPORT,
            $USER->id, \backup::TARGET_NEW_COURSE);
        $rc->execute_precheck();
        $rc->execute_plan();
        $rc->destroy();
        return $newid;
    }

    public function test_overrides_survive_backup_and_restore(): void {
        global $DB;

        $this->resetAfterTest();
        $this->setAdminUser();
        $course = $this->getDataGenerator()->create_course();
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiplinked', 'value' => '0']);
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiptargets', 'value' => '0']);

        $this->assertEquals(
            ['skiplinked' => '0', 'skiptargets' => '0'],
            $DB->get_records_menu('local_linearnav', ['courseid' => $this->copy($course)], 'name', 'name, value')
        );
    }

    public function test_old_includesections_restores_as_both_section_kinds(): void {
        global $DB;

        $this->resetAfterTest();
        $this->setAdminUser();
        $gen = $this->getDataGenerator();
        $off = $gen->create_course();
        $on = $gen->create_course();
        $DB->insert_record('local_linearnav', ['courseid' => $off->id, 'name' => 'includesections', 'value' => '0']);
        $DB->insert_record('local_linearnav', ['courseid' => $on->id, 'name' => 'includesections', 'value' => '1']);

        $this->assertEquals(
            ['includesubsections' => '0', 'includetopsections' => '0'],
            $DB->get_records_menu('local_linearnav', ['courseid' => $this->copy($off)], 'name', 'name, value')
        );
        $this->assertSame([], $DB->get_records_menu('local_linearnav', ['courseid' => $this->copy($on)]));
    }

    public function test_overrides_go_with_the_course(): void {
        global $DB;

        $this->resetAfterTest();
        $course = $this->getDataGenerator()->create_course();
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiplinked', 'value' => '0']);

        delete_course($course, false);

        $this->assertSame(0, $DB->count_records('local_linearnav', ['courseid' => $course->id]));
    }
}
