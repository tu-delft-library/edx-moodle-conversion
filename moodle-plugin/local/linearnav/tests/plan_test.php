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
 * Tests for the plan builder.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use PHPUnit\Framework\Attributes\CoversClass;

/**
 * Plan builder tests.
 */
#[CoversClass(plan::class)]
final class plan_test extends \advanced_testcase {
    /**
     * Course with A, stub B -> R1 in section 1, subsection with C and stub B' -> R1, R1 in section 3.
     *
     * @return array [$course, $a, $b, $c, $b2, $r1]
     */
    private function course_with_stubs(): array {
        global $CFG;

        $this->setAdminUser();
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 3], ['createsections' => true]);
        $a = $gen->create_module('page', ['course' => $course->id, 'section' => 1, 'name' => 'A']);
        $r1 = $gen->create_module('page', ['course' => $course->id, 'section' => 3, 'name' => 'R1']);
        $b = $gen->create_module('url', [
            'course' => $course->id,
            'section' => 1,
            'name' => 'B',
            'externalurl' => $CFG->wwwroot . '/mod/page/view.php?id=' . $r1->cmid,
        ]);
        $sub = $gen->create_module('subsection', ['course' => $course->id, 'section' => 2, 'name' => 'Sub']);
        $subsection = get_fast_modinfo($course)->get_cm($sub->cmid)->get_delegated_section_info();
        $c = $gen->create_module('page', ['course' => $course->id, 'section' => $subsection->section, 'name' => 'C']);
        $b2 = $gen->create_module('url', [
            'course' => $course->id,
            'section' => $subsection->section,
            'name' => "B'",
            'externalurl' => $CFG->wwwroot . '/mod/page/view.php?id=' . $r1->cmid,
        ]);
        return [$course, $a, $b, $c, $b2, $r1];
    }

    /**
     * Plan as [id, targetid] pairs in walk order.
     *
     * @param plan $plan
     * @return array
     */
    private function walk(plan $plan): array {
        return array_map(fn($k) => [$plan->get($k)['id'], $plan->get($k)['targetid']], $plan->keys());
    }

    public function test_stubs_walk_their_target_in_sidebar_order(): void {
        $this->resetAfterTest();
        set_config('skiplinked', 0, 'local_linearnav');
        [$course, $a, $b, $c, $b2, $r1] = $this->course_with_stubs();

        $plan = plan::for_course($course);

        $this->assertSame(
            [
                [(int) $a->cmid, (int) $a->cmid],
                [(int) $b->cmid, (int) $r1->cmid],
                [(int) $c->cmid, (int) $c->cmid],
                [(int) $b2->cmid, (int) $r1->cmid],
                [(int) $r1->cmid, (int) $r1->cmid],
            ],
            $this->walk($plan)
        );
        $this->assertCount(5, array_unique($plan->keys()));
    }

    public function test_skiplinked_drops_hidden_sections(): void {
        $this->resetAfterTest();
        $this->setAdminUser();
        $gen = $this->getDataGenerator();
        $course = $gen->create_course(['numsections' => 2], ['createsections' => true]);
        $shown = $gen->create_module('page', ['course' => $course->id, 'section' => 1]);
        $gen->create_module('page', ['course' => $course->id, 'section' => 2]);
        $hidden = get_fast_modinfo($course)->get_section_info(2);
        (new \core_courseformat\local\sectionactions($course))->set_visibility($hidden, false);

        set_config('skiplinked', 1, 'local_linearnav');
        $this->assertSame([[(int) $shown->cmid, (int) $shown->cmid]], $this->walk(plan::for_course($course)));
        set_config('skiplinked', 0, 'local_linearnav');
        $this->assertCount(2, $this->walk(plan::for_course($course)));
    }

    public function test_skiplinked_drops_stubs_their_targets_and_stub_only_sections(): void {
        global $CFG;

        $this->resetAfterTest();
        set_config('skiplinked', 1, 'local_linearnav');
        set_config('includetopsections', 1, 'local_linearnav');
        set_config('includesubsections', 1, 'local_linearnav');
        [$course, $a, , $c, , $r1] = $this->course_with_stubs();
        $gen = $this->getDataGenerator();
        $stubsub = $gen->create_module('subsection', ['course' => $course->id, 'section' => 3, 'name' => 'Stubs only']);
        $gen->create_module('url', [
            'course' => $course->id,
            'section' => get_fast_modinfo($course)->get_cm($stubsub->cmid)->get_delegated_section_info()->section,
            'externalurl' => $CFG->wwwroot . '/mod/page/view.php?id=' . $r1->cmid,
        ]);
        $modinfo = get_fast_modinfo($course);
        $sec = fn($n) => (int) $modinfo->get_section_info($n)->id;
        $sub = (int) $modinfo->get_cm($c->cmid)->get_section_info()->id;

        $plan = plan::for_course($course);
        $this->assertSame(
            [
                ['section', $sec(0)],
                ['section', $sec(1)],
                ['cm', (int) $a->cmid],
                ['section', $sec(2)],
                ['section', $sub],
                ['cm', (int) $c->cmid],
                ['section', $sec(3)],
            ],
            array_map(fn($k) => [$plan->get($k)['kind'], $plan->get($k)['id']], $plan->keys())
        );
    }

    public function test_course_override_beats_site_setting(): void {
        global $DB;

        $this->resetAfterTest();
        set_config('skiplinked', 0, 'local_linearnav');
        [$course, $a, , $c] = $this->course_with_stubs();
        $DB->insert_record('local_linearnav', ['courseid' => $course->id, 'name' => 'skiplinked', 'value' => '1']);

        $this->assertSame(
            [[(int) $a->cmid, (int) $a->cmid], [(int) $c->cmid, (int) $c->cmid]],
            $this->walk(plan::for_course($course))
        );
    }

    public function test_neighbours_follow_plan_not_page(): void {
        $this->resetAfterTest();
        set_config('skiplinked', 0, 'local_linearnav');
        [$course] = $this->course_with_stubs();
        $plan = plan::for_course($course);
        [, $second, $third, $fourth, $fifth] = $plan->keys();

        [$prev, $next] = $plan->neighbours($fifth);
        $this->assertSame($plan->get($fourth), $prev);
        $this->assertNull($next);
        [, $next] = $plan->neighbours($second);
        $this->assertSame($plan->get($third), $next);
    }

    public function test_sections_option_adds_section_entries_before_contents(): void {
        $this->resetAfterTest();
        set_config('skiplinked', 0, 'local_linearnav');
        set_config('includetopsections', 1, 'local_linearnav');
        set_config('includesubsections', 0, 'local_linearnav');
        [$course, $a, $b, $c, $b2, $r1] = $this->course_with_stubs();
        $modinfo = get_fast_modinfo($course);
        $sec = fn($n) => (int) $modinfo->get_section_info($n)->id;
        $sub = (int) $modinfo->get_cm($c->cmid)->get_section_info()->id;

        $kinds = fn(plan $p) => array_map(fn($k) => [$p->get($k)['kind'], $p->get($k)['id']], $p->keys());
        $this->assertSame(
            [
                ['section', $sec(0)],
                ['section', $sec(1)],
                ['cm', (int) $a->cmid],
                ['cm', (int) $b->cmid],
                ['section', $sec(2)],
                ['cm', (int) $c->cmid],
                ['cm', (int) $b2->cmid],
                ['section', $sec(3)],
                ['cm', (int) $r1->cmid],
            ],
            $kinds(plan::for_course($course))
        );

        set_config('includetopsections', 0, 'local_linearnav');
        set_config('includesubsections', 1, 'local_linearnav');
        $this->assertSame(
            [
                ['cm', (int) $a->cmid],
                ['cm', (int) $b->cmid],
                ['section', $sub],
                ['cm', (int) $c->cmid],
                ['cm', (int) $b2->cmid],
                ['cm', (int) $r1->cmid],
            ],
            $kinds(plan::for_course($course))
        );

        set_config('includesubsections', 0, 'local_linearnav');
        $this->assertCount(5, plan::for_course($course)->keys());
    }
}
