# Case studies and resources (admin guide)

## Case studies (`/case-studies/`)
Short, article-like write-ups of incidents and current threats. Every case
study has a **Description** and an **About** section (About can carry a
picture gallery), plus any number of extra sections whose headings come from
the admin-managed list under *Case studies → Section titles* ("Be careful of",
"How to identify", … — add your own).

* **Create / edit**: *Admin → Case studies → New case study*. Fill the Georgian
  tab (English optional), pick a category, upload a cover, tick *Published*.
  Sections and pictures are added on the edit page after the first save.
* **Categories**: *Admin → Case studies → Categories*. `ongoing-threats`
  ("მიმდინარე საფრთხეები") ships with the platform and feeds the home page.
* **Home page**: the "Ongoing threats" block shows the newest published case
  studies of the category named by the site setting
  `site.home_threats_category` (default `ongoing-threats`), at most
  `site.home_threats_limit` (default 4). The hero statistics count published
  case studies and the ones in that category.
* HTML in the text fields is sanitised (nh3 allow-list); `<img>` tags with
  same-origin or https sources are kept.

## Resources (`/resources/`)
* **Platform documents**: *Admin → Resources*. PDF only. *Shown/Hidden*
  toggles both the listing and the public file URL.
* **From courses**: files and links attached to lessons (instructor panel)
  are listed for signed-in learners with an active or completed enrolment in
  that course, grouped by course. They are never shown publicly.
