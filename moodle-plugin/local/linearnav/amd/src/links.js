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
 * Adds the plan key to activity name links right before they are followed.
 *
 * @module     local_linearnav/links
 * @copyright  2026 TU Delft
 * @license    http://www.gnu.org/copyleft/gpl.html GNU GPL v3 or later
 */

const CM_LINK = 'a[data-for="cm_name"], a.aalink';
const CM_ITEM = '[data-for="cm"][data-id], [data-for="cmitem"][data-id]';
const SECTION_LINK = 'a[data-for="section_title"], .sectionname a';
const SECTION_ITEM =
    '[data-for="section_title"][data-id], [data-for="section"][data-id]';

export const init = () => {
    const node = document.getElementById("local_linearnav-links");
    if (!node) {
        return;
    }
    const links = JSON.parse(node.textContent);

    const lookup = (target, link, item, prefix) => {
        const anchor = target.closest(link);
        const id = anchor?.closest(item)?.dataset.id;
        return id && links[prefix + id] ? [anchor, links[prefix + id]] : null;
    };

    const rewrite = (e) => {
        const hit =
            lookup(e.target, SECTION_LINK, SECTION_ITEM, "s") ||
            lookup(e.target, CM_LINK, CM_ITEM, "c");
        if (hit) {
            hit[0].href = hit[1];
        }
    };

    document.addEventListener("pointerdown", rewrite, true);
    document.addEventListener("focusin", rewrite, true);
};
