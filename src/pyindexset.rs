use hashbrown::HashTable;
use pyo3::{exceptions, prelude::*};

struct Slot {
    hash: u64,
    obj: PyObject,
}

enum SlotOrRemoved {
    Taken(Slot),
    Removed,
}

impl SlotOrRemoved {
    fn obj(&self) -> &PyObject {
        match self {
            SlotOrRemoved::Taken(slot) => &slot.obj,
            SlotOrRemoved::Removed => unreachable!(),
        }
    }

    fn hash(&self) -> u64 {
        match self {
            SlotOrRemoved::Taken(slot) => slot.hash,
            SlotOrRemoved::Removed => unreachable!(),
        }
    }
}

#[derive(Default)]
pub struct PyIndexSet {
    lookup: HashTable<usize>,
    objects: Vec<SlotOrRemoved>,
}

impl PyIndexSet {
    pub fn get_index(&self, index: usize) -> Option<&PyObject> {
        self.objects.get(index).map(|slot| slot.obj())
    }

    pub fn get_full(&self, obj: &Bound<'_, PyAny>) -> PyResult<Option<(usize, &PyObject)>> {
        let hash = obj.hash()? as u64;

        let mut res = Ok(());

        let index = self.lookup.find(hash, |&index| {
            if res.is_err() {
                false
            } else {
                match self.objects[index].obj().bind(obj.py()).eq(obj) {
                    Ok(is_eq) => is_eq,
                    Err(err) => {
                        res = Err(err);
                        false
                    }
                }
            }
        });

        res?;

        Ok(index.map(|&index| (index, self.objects[index].obj())))
    }

    pub fn remove(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<()> {
        let hash = obj.hash()? as u64;

        let mut res = Ok(());

        let entry = self.lookup.find_entry(hash, |&index| {
            if res.is_err() {
                false
            } else {
                match self.objects[index].obj().bind(obj.py()).eq(obj) {
                    Ok(is_eq) => is_eq,
                    Err(err) => {
                        res = Err(err);
                        false
                    }
                }
            }
        });

        res?;

        match entry {
            Ok(entry) => {
                let index = *entry.get();
                entry.remove();
                self.objects[index] = SlotOrRemoved::Removed;
                Ok(())

            },
            Err(absent) => Err(
                PyErr::new::<exceptions::PyKeyError, _>("Object not found in index set"),
            ),
        }
    }

    pub fn insert_full(&mut self, obj: &Bound<'_, PyAny>) -> PyResult<(usize, bool)> {
        let hash = obj.hash()? as u64;

        let mut res = Ok(());

        let entry = self.lookup.entry(
            hash,
            |&index| {
                if res.is_err() {
                    false
                } else {
                    match self.objects[index].obj().bind(obj.py()).eq(obj) {
                        Ok(is_eq) => is_eq,
                        Err(err) => {
                            res = Err(err);
                            false
                        }
                    }
                }
            },
            |&index| self.objects[index].hash(),
        );

        res?;

        match entry {
            hashbrown::hash_table::Entry::Occupied(entry) => Ok((*entry.get(), false)),
            hashbrown::hash_table::Entry::Vacant(entry) => {
                let index = self.objects.len();
                self.objects.push(SlotOrRemoved::Taken(Slot { hash, obj: obj.clone().unbind() }));
                entry.insert(index);

                Ok((index, true))
            }
        }
    }
}
