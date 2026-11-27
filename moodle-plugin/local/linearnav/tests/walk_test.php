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
 * Whole-course walks on the live test plan's fixture courses.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use PHPUnit\Framework\Attributes\CoversClass;
use PHPUnit\Framework\Attributes\DataProvider;
use core\hook\output\before_footer_html_generation;

defined('MOODLE_INTERNAL') || die();

global $CFG;
require_once($CFG->libdir . '/resourcelib.php');

/**
 * Walk tests, course A and B are the live plan's fixture.
 */
#[CoversClass(plan::class)]
#[CoversClass(hook_callbacks::class)]
final class walk_test extends \advanced_testcase
{
    /**
     * Course A: returns [course, name => module].
     *
     * @return array
     */
    private function course_a(): array
    {
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 6, 'enablecompletion' => 1], ['createsections' => true]);
        $page = fn ($s, $n, $x = []) => $gen->create_module('page', ['course' => $course->id, 'section' => $s, 'name' => $n] + $x);
        $cm['p0'] = $page(0, 'p0');
        $cm['p1'] = $page(1, 'p1');
        $gen->create_module('label', ['course' => $course->id, 'section' => 1, 'name' => 'L1', 'intro' => 'L1']);
        $cm['p2'] = $page(1, 'p2');
        $cm['R1'] = $page(3, 'R1');
        $cm['R2'] = $page(3, 'R2');
        $cm['U1'] = $this->stub($course, 1, 'U1', $cm['R1']);
        $cm['Q1'] = $gen->create_module('quiz', ['course' => $course->id, 'section' => 1, 'name' => 'Q1']);
        $cm['p3'] = $page(2, 'p3');
        $sub = $gen->create_module('subsection', ['course' => $course->id, 'section' => 2, 'name' => 'SUB']);
        $subnum = get_fast_modinfo($course)->get_cm($sub->cmid)->get_delegated_section_info()->section;
        $cm['p4'] = $page($subnum, 'p4');
        $cm['U2'] = $this->stub($course, $subnum, 'U2', $cm['p1']);
        $cm['p5'] = $page(2, 'p5');
        $cm['p6'] = $page(4, 'p6');
        $cm['U3'] = $this->stub($course, 5, 'U3', $cm['R2']);
        $cm['p7'] = $page(6, 'p7', ['availability' =>
            '{"op":"&","c":[{"type":"date","d":">=","t":4102444800}],"showc":[true]}']);
        $cm['p8'] = $page(6, 'p8', ['visible' => 0]);
        $hidden = get_fast_modinfo($course)->get_section_info(4);
        (new \core_courseformat\local\sectionactions($course))->set_visibility($hidden, false);
        $this->name_sections($course);

        // a fixture mistake must fail here, not look like a walk bug
        $this->assertSame([
            'S0' => ['p0'], 'S1' => ['p1', 'L1', 'p2', 'U1', 'Q1'], 'S2' => ['p3', 'SUB', 'p5'], 'S3' => ['R1', 'R2'],
            'S4' => ['p6'], 'S5' => ['U3'], 'S6' => ['p7', 'p8'], 'SUB' => ['p4', 'U2'],
        ], $this->layout($course));
        return [$course, $cm];
    }

    /**
     * Course B: R1 hidden in a hidden section, reachable through stub U1. Returns [course, name => module].
     *
     * @return array
     */
    private function course_b(): array
    {
        set_config('allowstealth', 1);
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 2, 'enablecompletion' => 1], ['createsections' => true]);
        $cm['p1'] = $gen->create_module('page', ['course' => $course->id, 'section' => 1, 'name' => 'p1']);
        $cm['R1'] = $gen->create_module('page', ['course' => $course->id, 'section' => 2, 'name' => 'R1']);
        $cm['U1'] = $this->stub($course, 1, 'U1', $cm['R1']);
        $cm['p2'] = $gen->create_module('page', ['course' => $course->id, 'section' => 1, 'name' => 'p2']);
        $hidden = get_fast_modinfo($course)->get_section_info(2);
        (new \core_courseformat\local\sectionactions($course))->set_visibility($hidden, false);
        set_coursemodule_visible($cm['R1']->cmid, 1, 0);
        $this->name_sections($course);

        $this->assertSame(['S0' => [], 'S1' => ['p1', 'U1', 'p2'], 'S2' => ['R1']], $this->layout($course));
        return [$course, $cm];
    }

    /**
     * Course C: parent-nested sections stored the way Authora stores them. Returns [course, name => module].
     *
     * @param array<int, int[]> $tree section number => [parent, order]
     * @param string $format format name the option rows are stored under
     * @return array
     */
    private function course_c(array $tree = [], string $format = 'topics'): array
    {
        global $DB;

        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 7], ['createsections' => true]);
        $page = fn ($s, $n) => $gen->create_module('page', ['course' => $course->id, 'section' => $s, 'name' => $n]);
        $cm['a1'] = $page(1, 'a1');
        $cm['c3'] = $page(3, 'c3');
        $sub = $gen->create_module('subsection', ['course' => $course->id, 'section' => 3, 'name' => 'SUB']);
        $subnum = get_fast_modinfo($course)->get_cm($sub->cmid)->get_delegated_section_info()->section;
        $cm['sp'] = $page($subnum, 'sp');
        $cm['gr'] = $page(4, 'gr');
        $cm['ab'] = $page(5, 'ab');
        $cm['w'] = $page(6, 'w');
        $cm['a7'] = $page(7, 'a7');
        $this->name_sections($course);

        $modinfo = get_fast_modinfo($course);
        $tree = $tree ?: [4 => [2, 3], 5 => [2, 2], 6 => [2, 1], 7 => [1, 1]];
        foreach ($tree as $number => [$parent, $order]) {
            foreach (['parent' => $parent, 'order' => $order] as $name => $value) {
                $DB->insert_record('course_format_options', [
                    'courseid' => $course->id,
                    'format' => $format,
                    'sectionid' => $modinfo->get_section_info($number)->id,
                    'name' => $name,
                    'value' => $value,
                ]);
            }
        }

        $this->assertSame([
            'S0' => [], 'S1' => ['a1'], 'S2' => [], 'S3' => ['c3', 'SUB'], 'S4' => ['gr'], 'S5' => ['ab'],
            'S6' => ['w'], 'S7' => ['a7'], 'SUB' => ['sp'],
        ], $this->layout($course));
        return [$course, $cm];
    }

    /**
     * Course D: page p1, file F1 set to open, external link X1, page p2. Returns the course.
     *
     * @return \stdClass
     */
    private function course_d(): \stdClass
    {
        $this->setAdminUser();
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 1], ['createsections' => true]);
        $gen->create_module('page', ['course' => $course->id, 'section' => 1, 'name' => 'p1']);
        $gen->create_module('resource', [
            'course' => $course->id, 'section' => 1, 'name' => 'F1', 'display' => RESOURCELIB_DISPLAY_OPEN,
        ]);
        $gen->create_module('url', [
            'course' => $course->id, 'section' => 1, 'name' => 'X1', 'externalurl' => 'https://example.com/x',
        ]);
        $gen->create_module('page', ['course' => $course->id, 'section' => 1, 'name' => 'p2']);
        $this->name_sections($course);
        return $course;
    }

    /**
     * Url activity pointing at a page in the same course.
     *
     * @param \stdClass $course
     * @param int $section
     * @param string $name
     * @param \stdClass $target
     * @return \stdClass
     */
    private function stub(\stdClass $course, int $section, string $name, \stdClass $target): \stdClass
    {
        global $CFG;

        return $this->getDataGenerator()->create_module('url', [
            'course' => $course->id,
            'section' => $section,
            'name' => $name,
            'externalurl' => $CFG->wwwroot . '/mod/page/view.php?id=' . $target->cmid,
        ]);
    }

    /**
     * Name sections S0, S1, ... and the delegated one SUB, so walks read like the plan's tables.
     *
     * @param \stdClass $course
     */
    private function name_sections(\stdClass $course): void
    {
        foreach (get_fast_modinfo($course)->get_section_info_all() as $section) {
            course_update_section($course, $section, ['name' => $section->is_delegated() ? 'SUB' : 'S' . $section->section]);
        }
    }

    /**
     * Section name => cm names in order.
     *
     * @param \stdClass $course
     * @return array<string, string[]>
     */
    private function layout(\stdClass $course): array
    {
        $modinfo = get_fast_modinfo($course);
        $layout = [];
        foreach ($modinfo->get_section_info_all() as $section) {
            $layout[$section->name] = array_map(
                fn ($cmid) => $modinfo->get_cm($cmid)->name,
                $modinfo->sections[$section->section] ?? []
            );
        }
        return $layout;
    }

    /**
     * Walk as names: stops by name, stubs as "U1/R1".
     *
     * @param \stdClass $course
     * @param plan $plan
     * @return string[]
     */
    private function names(\stdClass $course, plan $plan): array
    {
        $modinfo = get_fast_modinfo($course);
        return array_map(function (string $key) use ($plan, $modinfo) {
            $entry = $plan->get($key);
            if ($entry['kind'] === 'section' || $entry['id'] == $entry['targetid']) {
                return $entry['name'];
            }
            return $entry['name'] . '/' . $modinfo->get_cm($entry['targetid'])->name;
        }, $plan->keys());
    }

    /**
     * Footer hook output for a cm page opened at a url.
     *
     * @param \stdClass $course
     * @param int $cmid
     * @param \moodle_url $url
     * @return string
     */
    private function footer(\stdClass $course, int $cmid, \moodle_url $url): string
    {
        $_GET['lnav'] = $url->param('lnav') ?? '';
        $page = new \moodle_page();
        $page->set_cm(get_fast_modinfo($course)->get_cm($cmid), $course);
        $page->set_url($url);
        $page->set_pagelayout('incourse');
        $hook = new before_footer_html_generation($page->get_renderer('core'));
        hook_callbacks::before_footer($hook);
        return $hook->get_output();
    }

    /**
     * Site settings, then the user the walk is seen as.
     *
     * @param \stdClass $course
     * @param int $skip
     * @param int $top
     * @param int $sub
     * @param string $role
     * @param int $targets
     * @param string $order
     */
    private function as(
        \stdClass $course,
        int $skip,
        int $top,
        int $sub,
        string $role,
        int $targets = 1,
        string $order = 'auto',
    ): void {
        set_config('skiplinked', $skip, 'local_linearnav');
        set_config('skiptargets', $targets, 'local_linearnav');
        set_config('includetopsections', $top, 'local_linearnav');
        set_config('includesubsections', $sub, 'local_linearnav');
        set_config('sectionorder', $order, 'local_linearnav');
        set_config('skipfiles', 0, 'local_linearnav');
        if ($role === 'admin') {
            $this->setAdminUser();
        } else {
            $this->setUser($this->getDataGenerator()->create_and_enrol($course));
        }
    }

    /**
     * Tables 5 and 6 of the live plan.
     *
     * @return array
     */
    public static function walk_provider(): array
    {
        return [
            '2.1 A skip on, student' => ['a', 1, 0, 0, 'student', 'p0 p2 Q1 p3 p4 p5'],
            '2.2 A skip on, admin' => ['a', 1, 0, 0, 'admin', 'p0 p2 Q1 p3 p4 p5 p7 p8'],
            '2.3 A skip off, student' => ['a', 0, 0, 0, 'student', 'p0 p1 p2 U1/R1 Q1 p3 p4 U2/p1 p5 R1 R2 U3/R2'],
            '2.4 A skip off, admin' => ['a', 0, 0, 0, 'admin', 'p0 p1 p2 U1/R1 Q1 p3 p4 U2/p1 p5 R1 R2 p6 U3/R2 p7 p8'],
            '2.5 A skip on, top, student' => ['a', 1, 1, 0, 'student', 'S0 p0 S1 p2 Q1 S2 p3 p4 p5 S3 S6'],
            '2.6 A skip on, sub, student' => ['a', 1, 0, 1, 'student', 'p0 p2 Q1 p3 SUB p4 p5'],
            '2.7 A skip off, top, sub, student' => ['a', 0, 1, 1, 'student',
                'S0 p0 S1 p1 p2 U1/R1 Q1 S2 p3 SUB p4 U2/p1 p5 S3 R1 R2 S5 U3/R2 S6'],
            '2.8 A skip off, top, sub, admin' => ['a', 0, 1, 1, 'admin',
                'S0 p0 S1 p1 p2 U1/R1 Q1 S2 p3 SUB p4 U2/p1 p5 S3 R1 R2 S4 p6 S5 U3/R2 S6 p7 p8'],
            '2.9 B skip off, student' => ['b', 0, 0, 0, 'student', 'p1 U1/R1 p2'],
            '2.10 B skip off, admin' => ['b', 0, 0, 0, 'admin', 'p1 U1/R1 p2 R1'],
            '2.11 B skip on, student' => ['b', 1, 0, 0, 'student', 'p1 p2'],
            'A skip on, targets kept, student' => ['a', 1, 0, 0, 'student', 'p0 p1 p2 Q1 p3 p4 p5 R1 R2', 0],
            'A skip on, targets kept, admin' => ['a', 1, 0, 0, 'admin', 'p0 p1 p2 Q1 p3 p4 p5 R1 R2 p7 p8', 0],
            'A skip off, targets setting ignored' => ['a', 0, 0, 0, 'student',
                'p0 p1 p2 U1/R1 Q1 p3 p4 U2/p1 p5 R1 R2 U3/R2', 0],
            'B skip on, targets kept, student' => ['b', 1, 0, 0, 'student', 'p1 p2', 0],
        ];
    }

    #[DataProvider('walk_provider')]
    public function test_walk(
        string $which,
        int $skip,
        int $top,
        int $sub,
        string $role,
        string $expected,
        int $targets = 1,
    ): void {
        $this->resetAfterTest();
        [$course] = $which === 'a' ? $this->course_a() : $this->course_b();
        $this->as($course, $skip, $top, $sub, $role, $targets);
        $plan = plan::for_course($course);
        $keys = $plan->keys();

        $this->assertSame(explode(' ', $expected), $this->names($course, $plan));
        $this->assertSame($keys, array_values(array_unique($keys)));
        foreach ($keys as $i => $key) {
            [$prev, $next] = $plan->neighbours($key);
            $this->assertSame($keys[$i - 1] ?? null, $prev['key'] ?? null);
            $this->assertSame($keys[$i + 1] ?? null, $next['key'] ?? null);
        }
    }

    public function test_every_real_stop_keyless_matches_keyed(): void
    {
        $this->resetAfterTest();
        [$course] = $this->course_a();
        $this->as($course, 0, 0, 0, 'student');
        $plan = plan::for_course($course);

        $checked = 0;
        foreach ($plan->keys() as $key) {
            $entry = $plan->get($key);
            if ($entry['id'] != $entry['targetid']) {
                continue;
            }
            $keyless = new \moodle_url($entry['url']);
            $keyless->remove_params('lnav');
            $keyed = $this->footer($course, $entry['id'], $entry['url']);
            $this->assertStringContainsString('local-linearnav', $keyed);
            $this->assertSame($keyed, $this->footer($course, $entry['id'], $keyless), $entry['name']);
            $checked++;
        }
        $this->assertSame(9, $checked);
    }

    public function test_keyless_hidden_target_falls_back_to_its_stub(): void
    {
        $this->resetAfterTest();
        [$course, $cm] = $this->course_b();
        $r1 = $cm['R1']->cmid;
        $url = new \moodle_url('/mod/page/view.php', ['id' => $r1]);
        $next = fn ($name) => 'id=' . $cm[$name]->cmid . '&amp;lnav=';

        // student cannot see R1, its only stop is stub U1
        $this->as($course, 0, 0, 0, 'student');
        $html = $this->footer($course, $r1, $url);
        $this->assertStringContainsString($next('p1'), $html);
        $this->assertStringContainsString($next('p2'), $html);

        // admin sees R1 as its own stop at the end
        $this->setAdminUser();
        $html = $this->footer($course, $r1, $url);
        $this->assertStringContainsString($next('p2'), $html);
        $this->assertStringNotContainsString('btn-primary', $html);

        // skip on drops R1 and U1 for the student
        $this->as($course, 1, 0, 0, 'student');
        $this->assertStringNotContainsString('local-linearnav', $this->footer($course, $r1, $url));
    }

    public function test_course_override_keeps_targets(): void
    {
        global $DB;

        $this->resetAfterTest();
        [$course] = $this->course_a();
        $this->as($course, 1, 0, 0, 'student');
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiptargets', 'value' => '0']);

        $this->assertSame(
            explode(' ', 'p0 p1 p2 Q1 p3 p4 p5 R1 R2'),
            $this->names($course, plan::for_course($course))
        );
    }

    public function test_course_override_beats_site(): void
    {
        global $DB;

        $this->resetAfterTest();
        [$course] = $this->course_a();
        $this->as($course, 1, 0, 0, 'student');
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiplinked', 'value' => '0']);

        $this->assertSame(
            explode(' ', 'p0 p1 p2 U1/R1 Q1 p3 p4 U2/p1 p5 R1 R2 U3/R2'),
            $this->names($course, plan::for_course($course))
        );
    }

    /**
     * Walks of course C per sectionorder value and tree shape.
     *
     * @return array
     */
    public static function tree_provider(): array
    {
        $facade = [4 => [2, 3], 5 => [2, 2], 6 => [2, 1], 7 => [1, 1]];
        return [
            'auto follows the tree' => [$facade, 'auto', 0, 0, 'a1 a7 w ab gr c3 sp'],
            'tree same as auto' => [$facade, 'tree', 0, 0, 'a1 a7 w ab gr c3 sp'],
            'treedesc reverses siblings only' => [$facade, 'treedesc', 0, 0, 'a1 a7 gr ab w c3 sp'],
            'core ignores the tree' => [$facade, 'core', 0, 0, 'a1 c3 sp gr ab w a7'],
            'top and sub stops' => [$facade, 'auto', 1, 1, 'S0 S1 a1 S7 a7 S2 S6 w S5 ab S4 gr S3 c3 SUB sp'],
            'top stops only' => [$facade, 'auto', 1, 0, 'S0 S1 a1 a7 S2 w ab gr S3 c3 sp'],
            'order ties fall back to number' => [[4 => [2, 0], 5 => [2, 0], 6 => [2, 0]], 'auto', 0, 0,
                'a1 gr ab w c3 sp a7'],
            'orphan parent is top level' => [[7 => [99, 1]], 'auto', 0, 0, 'a1 c3 sp gr ab w a7'],
            'own parent is top level' => [[7 => [7, 1]], 'auto', 0, 0, 'a1 c3 sp gr ab w a7'],
            'cycle walked once as top level' => [[4 => [5, 1], 5 => [4, 1], 6 => [2, 1]], 'auto', 0, 0,
                'a1 w c3 sp a7 gr ab'],
            'no parent anywhere is today\'s walk' => [[7 => [0, 5]], 'auto', 0, 0, 'a1 c3 sp gr ab w a7'],
        ];
    }

    #[DataProvider('tree_provider')]
    public function test_tree_walk(array $tree, string $order, int $top, int $sub, string $expected): void
    {
        $this->resetAfterTest();
        [$course] = $this->course_c($tree);
        $this->as($course, 1, $top, $sub, 'student', 1, $order);
        $plan = plan::for_course($course);
        $keys = $plan->keys();

        $this->assertSame(explode(' ', $expected), $this->names($course, $plan));
        $this->assertSame($keys, array_values(array_unique($keys)));
    }

    public function test_tree_hidden_child_is_left_out(): void
    {
        $this->resetAfterTest();
        [$course] = $this->course_c();
        $hidden = get_fast_modinfo($course)->get_section_info(5);
        (new \core_courseformat\local\sectionactions($course))->set_visibility($hidden, false);

        $this->as($course, 1, 0, 0, 'student');
        $this->assertSame(explode(' ', 'a1 a7 w gr c3 sp'), $this->names($course, plan::for_course($course)));
        $this->as($course, 0, 0, 0, 'admin');
        $this->assertSame(explode(' ', 'a1 a7 w ab gr c3 sp'), $this->names($course, plan::for_course($course)));
    }

    public function test_tree_rows_of_another_format_are_ignored(): void
    {
        $this->resetAfterTest();
        [$course] = $this->course_c([], 'multitabs');
        $this->as($course, 1, 0, 0, 'student');

        $this->assertSame(explode(' ', 'a1 c3 sp gr ab w a7'), $this->names($course, plan::for_course($course)));
    }

    public function test_tree_course_override_beats_site(): void
    {
        global $DB;

        $this->resetAfterTest();
        [$course] = $this->course_c();
        $this->as($course, 1, 0, 0, 'student');
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'sectionorder', 'value' => 'core']);

        $this->assertSame(explode(' ', 'a1 c3 sp gr ab w a7'), $this->names($course, plan::for_course($course)));
    }

    public function test_tree_keyless_child_page_gets_tree_neighbours(): void
    {
        $this->resetAfterTest();
        [$course, $cm] = $this->course_c();
        $this->as($course, 1, 0, 0, 'student');
        $url = new \moodle_url('/mod/page/view.php', ['id' => $cm['ab']->cmid]);
        $html = $this->footer($course, $cm['ab']->cmid, $url);

        $this->assertStringContainsString('id=' . $cm['w']->cmid . '&amp;lnav=', $html);
        $this->assertStringContainsString('id=' . $cm['gr']->cmid . '&amp;lnav=', $html);
    }

    public function test_files_and_links_open_their_own_page(): void
    {
        $this->resetAfterTest();
        $course = $this->course_d();
        $this->as($course, 1, 0, 0, 'student');
        $plan = plan::for_course($course);
        $forceview = array_map(fn ($key) => $plan->get($key)['url']->param('forceview'), $plan->keys());

        $this->assertSame(['p1', 'F1', 'X1', 'p2'], $this->names($course, $plan));
        $this->assertSame([null, '1', '1', null], $forceview);
    }

    public function test_skipfiles_leaves_files_out(): void
    {
        global $DB;

        $this->resetAfterTest();
        $course = $this->course_d();
        $this->as($course, 1, 0, 0, 'student');
        set_config('skipfiles', 1, 'local_linearnav');
        $this->assertSame(['p1', 'X1', 'p2'], $this->names($course, plan::for_course($course)));

        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skipfiles', 'value' => '0']);
        $this->assertSame(['p1', 'F1', 'X1', 'p2'], $this->names($course, plan::for_course($course)));
    }
}
