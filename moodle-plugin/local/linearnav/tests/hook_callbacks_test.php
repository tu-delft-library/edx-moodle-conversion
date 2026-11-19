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
 * Tests for the footer hook.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use PHPUnit\Framework\Attributes\CoversClass;
use core\hook\output\before_footer_html_generation;
use core\hook\output\before_http_headers;

/**
 * Footer hook tests.
 */
#[CoversClass(hook_callbacks::class)]
final class hook_callbacks_test extends \advanced_testcase {
    /**
     * Run the hook on a fresh page for a cm and an `lnav` value.
     *
     * @param \stdClass $course
     * @param int $cmid
     * @param string $lnav
     * @return string hook output
     */
    private function footer(\stdClass $course, int $cmid, string $lnav): string {
        $hook = new before_footer_html_generation($this->page($course, $cmid, $lnav)->get_renderer('core'));
        hook_callbacks::before_footer($hook);
        return $hook->get_output();
    }

    /**
     * Fresh page for a cm, with `lnav` set in the request.
     *
     * @param \stdClass $course
     * @param int $cmid
     * @param string $lnav
     * @return \moodle_page
     */
    private function page(\stdClass $course, int $cmid, string $lnav): \moodle_page {
        $_GET['lnav'] = $lnav;
        $page = new \moodle_page();
        $page->set_cm(get_fast_modinfo($course)->get_cm($cmid), $course);
        $page->set_url('/mod/page/view.php', ['id' => $cmid]);
        $page->set_pagelayout('incourse');
        return $page;
    }

    public function test_footer_only_with_matching_key(): void {
        $this->resetAfterTest();
        $this->setAdminUser();
        $gen = $this->getDataGenerator();
        $course = $gen->create_course();
        $a = $gen->create_module('page', ['course' => $course->id, 'section' => 0]);
        $b = $gen->create_module('page', ['course' => $course->id, 'section' => 0]);
        [$ka] = plan::for_course($course)->keys();

        $this->assertStringNotContainsString('local-linearnav', $this->footer($course, $a->cmid, ''));
        $this->assertStringNotContainsString('local-linearnav', $this->footer($course, $b->cmid, $ka));
        $this->assertStringContainsString('id=' . $b->cmid . '&amp;lnav=', $this->footer($course, $a->cmid, $ka));
    }

    public function test_stub_marked_viewed_when_target_opened(): void {
        global $CFG;

        $this->resetAfterTest();
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['enablecompletion' => 1]);
        $student = $gen->create_and_enrol($course, 'student');
        $r1 = $gen->create_module('page', ['course' => $course->id, 'section' => 0]);
        $stub = $gen->create_module('url', [
            'course' => $course->id,
            'section' => 0,
            'externalurl' => $CFG->wwwroot . '/mod/page/view.php?id=' . $r1->cmid,
            'completion' => COMPLETION_TRACKING_AUTOMATIC,
            'completionview' => COMPLETION_VIEW_REQUIRED,
        ]);
        set_config('skiplinked', 0, 'local_linearnav');
        $this->setUser($student);
        [, $kstub] = plan::for_course($course)->keys();

        hook_callbacks::before_http_headers(
            new before_http_headers($this->page($course, $r1->cmid, $kstub)->get_renderer('core'))
        );

        $stubcm = get_fast_modinfo($course)->get_cm($stub->cmid);
        $this->assertEquals(COMPLETION_COMPLETE, (new \completion_info($course))->get_data($stubcm)->completionstate);
    }

    public function test_footer_on_section_page(): void {
        $this->resetAfterTest();
        $this->setAdminUser();
        set_config('includesections', 1, 'local_linearnav');
        set_config('includetopsections', 1, 'local_linearnav');
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 1], ['createsections' => true]);
        $a = $gen->create_module('page', ['course' => $course->id, 'section' => 1]);
        $plan = plan::for_course($course);
        $key = $plan->keys()[1];
        $sectionid = $plan->get($key)['targetid'];

        $_GET['lnav'] = $key;
        $page = new \moodle_page();
        $page->set_course($course);
        $page->set_url('/course/section.php', ['id' => $sectionid]);
        $page->set_pagelayout('course');
        $hook = new before_footer_html_generation($page->get_renderer('core'));
        hook_callbacks::before_footer($hook);

        $this->assertStringContainsString('id=' . $a->cmid . '&amp;lnav=', $hook->get_output());
    }
}
