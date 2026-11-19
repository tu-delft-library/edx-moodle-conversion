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
 * Hook callbacks.
 *
 * @package    local_linearnav
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

namespace local_linearnav;

use core\hook\output\before_footer_html_generation;
use core\hook\output\before_http_headers;
use core\output\supplementary_sticky_footer;
use html_writer;

/**
 * Renders the plan footer and ships the link map to the page.
 */
final class hook_callbacks {
    /** @var \WeakMap<\moodle_page, plan> plan per page, so both hooks of one request share it */
    private static ?\WeakMap $plans = null;

    /**
     * Replace core linear navigation with the plan footer on course pages.
     *
     * @param before_footer_html_generation $hook
     */
    public static function before_footer(before_footer_html_generation $hook): void {
        $page = $hook->renderer->get_page();
        if ($page->course->id == SITEID || !in_array($page->pagelayout, ['course', 'incourse'], true)) {
            return;
        }

        $page->set_show_navigation_footer(false);
        $plan = self::plan($page);

        $hook->add_html(html_writer::tag(
            'script',
            json_encode($plan->link_map(), JSON_HEX_TAG | JSON_HEX_AMP),
            ['type' => 'application/json', 'id' => 'local_linearnav-links']
        ));
        $page->requires->js_call_amd('local_linearnav/links', 'init');

        $entry = $plan->get(optional_param('lnav', '', PARAM_ALPHANUM));
        if ($entry === null || !self::is_current($page, $entry) || $page->has_sticky_footer()) {
            return;
        }

        [$prev, $next] = $plan->neighbours($entry['key']);
        $content = $hook->renderer->render_from_template('local_linearnav/footer', [
            'prev' => $prev ? ['url' => $prev['url']->out(false), 'name' => $prev['name']] : null,
            'next' => $next ? ['url' => $next['url']->out(false), 'name' => $next['name']] : null,
            'courseurl' => (new \moodle_url('/course/view.php', ['id' => $page->course->id]))->out(false),
        ]);
        $hook->add_html($hook->renderer->render(new supplementary_sticky_footer($content, 'local-linearnav')));
    }

    /**
     * Mark a stub viewed when its target page is opened through it, its own view.php is skipped.
     *
     * Runs before headers because completion must be set before any output.
     *
     * @param before_http_headers $hook
     */
    public static function before_http_headers(before_http_headers $hook): void {
        $page = $hook->renderer->get_page();
        $key = optional_param('lnav', '', PARAM_ALPHANUM);
        if ($key === '' || $page->cm === null) {
            return;
        }
        $entry = self::plan($page)->get($key);
        $isstub = $entry !== null && $entry['kind'] === 'cm' && $entry['id'] != $entry['targetid'];
        if (!$isstub || !self::is_current($page, $entry)) {
            return;
        }
        $stub = get_fast_modinfo($page->course)->get_cm($entry['id']);
        (new \completion_info($page->course))->set_module_viewed($stub);
    }

    /**
     * Plan for the page's course, built once per page.
     *
     * @param \moodle_page $page
     * @return plan
     */
    private static function plan(\moodle_page $page): plan {
        self::$plans ??= new \WeakMap();
        return self::$plans[$page] ??= plan::for_course($page->course);
    }

    /**
     * Whether the page being rendered is the one the entry opens.
     *
     * @param \moodle_page $page
     * @param array $entry
     * @return bool
     */
    private static function is_current(\moodle_page $page, array $entry): bool {
        if ($entry['kind'] === 'section') {
            return str_ends_with($page->url->get_path(), '/course/section.php')
                && $page->url->param('id') == $entry['targetid'];
        }
        return $page->cm !== null && $page->cm->id == $entry['targetid'];
    }
}
