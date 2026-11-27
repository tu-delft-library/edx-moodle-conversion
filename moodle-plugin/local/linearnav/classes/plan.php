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
 * Ordered walk over the course index, with stubs resolved to the page they point at.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use core_course\modinfo;
use core_course\section_info;
use moodle_url;

/**
 * Linear plan of a course as the current user sees it in the course index.
 */
final class plan {
    /** @var string[] values of the sectionorder setting */
    public const SECTIONORDERS = ['auto', 'core', 'tree', 'treedesc'];

    /** @var array<string, array> key => entry */
    private array $entries = [];

    /** @var string[] keys in walk order */
    private array $order = [];

    /** @var array<int, true> section ids already walked, so a parent cycle can't repeat a section */
    private array $walked = [];

    /** @var array<int, true> section numbers that are a child in the parent tree */
    private array $nested = [];

    /**
     * Use {@see for_course()}.
     *
     * @param modinfo $modinfo
     * @param array<int, int> $targets stub cmid => target cmid
     * @param array<int, int> $linked target cmid => stub cmid, empty when linked pages are kept
     * @param bool $skiplinked
     * @param bool $topsections add top-level sections as entries
     * @param bool $subsections add subsections as entries
     * @param bool $skipfiles leave file activities out
     * @param array<int, int[]> $children parent section number => child section numbers in walk order
     */
    private function __construct(
        private readonly modinfo $modinfo,
        private readonly array $targets,
        private readonly array $linked,
        private readonly bool $skiplinked,
        private readonly bool $topsections,
        private readonly bool $subsections,
        private readonly bool $skipfiles,
        private readonly array $children,
    ) {
        foreach ($children as $numbers) {
            $this->nested += array_fill_keys($numbers, true);
        }
    }

    /**
     * Build the plan for a course and the current user.
     *
     * @param \stdClass $course
     * @return self
     */
    public static function for_course(\stdClass $course): self {
        global $DB;

        $modinfo = get_fast_modinfo($course);
        $urls = $DB->get_records_menu('url', ['course' => $course->id], '', 'id, externalurl');
        $targets = self::stub_targets($modinfo, $urls);
        $config = course_settings::for_course((int) $course->id);
        $skiplinked = !empty($config->skiplinked);
        [$roots, $children] = self::section_tree($course, $modinfo, (string) ($config->sectionorder ?? 'auto'));

        $plan = new self(
            $modinfo,
            $targets,
            $skiplinked && !empty($config->skiptargets) ? array_flip($targets) : [],
            $skiplinked,
            !empty($config->includetopsections),
            !empty($config->includesubsections),
            !empty($config->skipfiles),
            $children,
        );
        foreach ($roots as $number) {
            $plan->walk($modinfo->get_section_info($number));
        }
        return $plan;
    }

    /**
     * Top-level section numbers and children per parent, from the format's parent and order options.
     *
     * Formats like flexsections and Authora (multitabs) nest sections through a 'parent' option instead of
     * subsection activities. Without any parent set, or in 'core' mode, every section is top level in number order.
     *
     * @param \stdClass $course
     * @param modinfo $modinfo
     * @param string $mode one of SECTIONORDERS
     * @return array{0: int[], 1: array<int, int[]>} [top-level numbers, parent number => child numbers]
     */
    private static function section_tree(\stdClass $course, modinfo $modinfo, string $mode): array {
        global $DB;

        $numbers = [];
        foreach ($modinfo->get_section_info_all() as $section) {
            if (!$section->is_delegated()) {
                $numbers[$section->id] = $section->section;
            }
        }
        $options = ['parent' => [], 'order' => []];
        if ($mode !== 'core') {
            $rows = $DB->get_records_select(
                'course_format_options',
                "courseid = :courseid AND format = :format AND name IN ('parent', 'order')",
                ['courseid' => $course->id, 'format' => $course->format],
                '',
                'id, sectionid, name, value'
            );
            foreach ($rows as $row) {
                if (isset($numbers[$row->sectionid])) {
                    $options[$row->name][$numbers[$row->sectionid]] = (int) $row->value;
                }
            }
        }
        if (!array_filter($options['parent'])) {
            return [array_values($numbers), []];
        }

        $known = array_flip($numbers);
        $roots = [];
        $children = [];
        foreach ($numbers as $number) {
            $parent = $options['parent'][$number] ?? 0;
            if ($parent === 0 || $parent === $number || !isset($known[$parent])) {
                $roots[] = $number;
            } else {
                $children[$parent][] = $number;
            }
        }
        $order = $options['order'];
        $sign = $mode === 'treedesc' ? -1 : 1;
        $children = array_map(function (array $siblings) use ($order, $sign): array {
            usort($siblings, fn($a, $b) => $sign * (($order[$a] ?? 0) <=> ($order[$b] ?? 0)) ?: $a <=> $b);
            return $siblings;
        }, $children);

        // A parent cycle has no way in from a top-level section, walk its sections as top level.
        $reached = [];
        $stack = $roots;
        while ($stack) {
            $number = array_pop($stack);
            $reached[$number] = true;
            array_push($stack, ...($children[$number] ?? []));
        }
        foreach ($numbers as $number) {
            if (!isset($reached[$number])) {
                $roots[] = $number;
            }
        }
        return [$roots, $children];
    }

    /**
     * Map stub cmid => target page cmid for url activities pointing at a page in the same course.
     *
     * @param modinfo $modinfo
     * @param array<int, string> $urls url instance id => externalurl
     * @return array<int, int>
     */
    public static function stub_targets(modinfo $modinfo, array $urls): array {
        global $CFG;

        $pattern = '#^' . preg_quote($CFG->wwwroot, '#') . '/mod/page/view\.php\?id=(\d+)$#';
        $cms = $modinfo->get_cms();
        $targets = [];
        foreach ($modinfo->get_instances_of('url') as $instanceid => $cm) {
            if (preg_match($pattern, $urls[$instanceid] ?? '', $m) && isset($cms[(int) $m[1]])) {
                $targets[(int) $cm->id] = (int) $m[1];
            }
        }
        return $targets;
    }

    /**
     * Append a section (when enabled for its kind) and its contents, then its child sections.
     *
     * @param section_info $section
     */
    private function walk(section_info $section): void {
        if (isset($this->walked[$section->id])) {
            return;
        }
        $this->walked[$section->id] = true;
        if (!$section->uservisible || ($this->skiplinked && !$section->visible)) {
            return;
        }
        $nested = $section->is_delegated() || isset($this->nested[$section->section]);
        $stop = $nested ? $this->subsections : $this->topsections;
        if ($stop && !($this->skiplinked && $this->only_stubs($section))) {
            $this->add('section', (int) $section->id, (int) $section->id,
                get_section_name($section->course, $section), new moodle_url('/course/section.php', ['id' => $section->id]));
        }
        foreach ($section->get_sequence_cm_infos() as $cm) {
            $delegated = $cm->get_delegated_section_info();
            if ($delegated) {
                $this->walk($delegated);
                continue;
            }
            $linked = isset($this->targets[$cm->id]) || isset($this->linked[$cm->id]);
            $skipped = ($this->skiplinked && $linked) || ($this->skipfiles && $cm->modname === 'resource');
            if (!$cm->uservisible || !$cm->get_navigation_url() || $skipped) {
                continue;
            }
            $target = isset($this->targets[$cm->id]) ? $this->modinfo->get_cm($this->targets[$cm->id]) : $cm;
            if ($target->uservisible) {
                $this->add('cm', (int) $cm->id, (int) $target->id, $cm->get_formatted_name(),
                    $target->get_navigation_url());
            }
        }
        foreach ($this->children[$section->section] ?? [] as $number) {
            $this->walk($this->modinfo->get_section_info($number));
        }
    }

    /**
     * Whether every linkable activity directly in a section is a stub.
     *
     * @param section_info $section
     * @return bool
     */
    private function only_stubs(section_info $section): bool {
        $ids = [];
        foreach ($section->get_sequence_cm_infos() as $cm) {
            if (!$cm->get_delegated_section_info() && $cm->url) {
                $ids[] = (int) $cm->id;
            }
        }
        return $ids && !array_diff($ids, array_keys($this->targets));
    }

    /**
     * Append one entry.
     *
     * @param string $kind 'cm' or 'section'
     * @param int $id the cm or section as listed in the course index
     * @param int $targetid the cm or section actually opened, differs from $id for stubs
     * @param string $name
     * @param moodle_url $url
     */
    private function add(string $kind, int $id, int $targetid, string $name, moodle_url $url): void {
        $key = substr(sha1($kind . $id . ':' . count($this->order)), 0, 12);
        $this->order[] = $key;
        $this->entries[$key] = [
            'key' => $key,
            'kind' => $kind,
            'id' => $id,
            'targetid' => $targetid,
            'name' => $name,
            'url' => new moodle_url($url, ['lnav' => $key]),
        ];
    }

    /**
     * Entry for a key.
     *
     * @param string $key
     * @return array|null
     */
    public function get(string $key): ?array {
        return $this->entries[$key] ?? null;
    }

    /**
     * Previous and next entry of a key that is in the plan.
     *
     * @param string $key
     * @return array{0: ?array, 1: ?array}
     */
    public function neighbours(string $key): array {
        $i = array_search($key, $this->order, true);
        return [
            $this->entries[$this->order[$i - 1] ?? ''] ?? null,
            $this->entries[$this->order[$i + 1] ?? ''] ?? null,
        ];
    }

    /**
     * Clicked item => url carrying its key, for the link rewriter. Keys are 'c<cmid>' and 's<sectionid>'.
     *
     * @return array<string, string>
     */
    public function link_map(): array {
        $map = [];
        foreach ($this->entries as $entry) {
            $map[$entry['kind'][0] . $entry['id']] = $entry['url']->out(false);
        }
        return $map;
    }

    /**
     * Keys in walk order.
     *
     * @return string[]
     */
    public function keys(): array {
        return $this->order;
    }
}
